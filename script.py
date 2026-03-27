import argparse
import csv
import os
from datetime import datetime, time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")

import django

django.setup()

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from apontamento_montagem.models import PecasOrdem
from core.models import OrdemProcesso
from inspecao.models import Inspecao


MAQUINAS_ALVO = {"serralheria", "transbordo", "roçadeira"}


def parse_args():
    hoje = timezone.localdate()
    inicio_padrao = hoje.replace(month=1, day=1)

    parser = argparse.ArgumentParser(
        description=(
            "Lista ordens de montagem finalizadas na máquina serralheria."
        )
    )
    parser.add_argument(
        "--inicio",
        default=inicio_padrao.isoformat(),
        help="Data inicial no formato YYYY-MM-DD. Padrão: 1º de janeiro do ano atual.",
    )
    parser.add_argument(
        "--fim",
        default=hoje.isoformat(),
        help="Data final no formato YYYY-MM-DD. Padrão: hoje.",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Caminho opcional para exportar os resultados em CSV.",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Cria as inspeções faltantes. Sem esta flag, roda apenas em simulação.",
    )
    return parser.parse_args()


def parse_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"{label} inválida: {value}. Use YYYY-MM-DD.") from exc


def format_datetime(value):
    if not value:
        return ""
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def format_date(value):
    if not value:
        return ""
    return value.strftime("%d/%m/%Y")


def split_peca(texto):
    valor = str(texto or "").strip()
    if " - " in valor:
        codigo, descricao = valor.split(" - ", maxsplit=1)
        return codigo.strip(), descricao.strip()
    return valor, ""


def map_real_finalization_dates(items):
    items_by_order = {}
    for item in items:
        items_by_order.setdefault(item.ordem_id, []).append(item)

    for order_items in items_by_order.values():
        order_items.sort(key=lambda item: item.id)

    order_ids = list(items_by_order.keys())
    processos = (
        OrdemProcesso.objects.filter(ordem_id__in=order_ids, status="finalizada")
        .order_by("ordem_id", "data_fim", "id")
        .only("id", "ordem_id", "data_fim")
    )

    processos_by_order = {}
    for processo in processos:
        processos_by_order.setdefault(processo.ordem_id, []).append(processo)

    data_real_por_item = {}
    for ordem_id, order_items in items_by_order.items():
        processos_finalizados = processos_by_order.get(ordem_id, [])

        for index, item in enumerate(order_items):
            data_real = None
            if index < len(processos_finalizados):
                data_real = processos_finalizados[index].data_fim
            elif item.processo_ordem and item.processo_ordem.status == "finalizada":
                data_real = item.processo_ordem.data_fim

            data_real_por_item[item.id] = data_real

    return data_real_por_item


def fetch_missing_items(data_inicio, data_fim):
    tz = timezone.get_current_timezone()
    inicio_dt = timezone.make_aware(datetime.combine(data_inicio, time.min), tz)
    fim_dt = timezone.make_aware(datetime.combine(data_fim, time.max), tz)

    qs = (
        PecasOrdem.objects.select_related(
            "ordem",
            "ordem__maquina",
            "ordem__operador_final",
            "processo_ordem",
        )
        .annotate(maquina_normalizada=Lower(Trim(F("ordem__maquina__nome"))))
        .filter(
            ordem__grupo_maquina="montagem",
            qtd_boa__gt=0,
            maquina_normalizada__in=MAQUINAS_ALVO,
        )
        .order_by("ordem__ordem", "id")
    )

    ids_inspecionados = set(
        Inspecao.objects.filter(
            pecas_ordem_montagem_id__in=qs.values_list("id", flat=True)
        ).values_list("pecas_ordem_montagem_id", flat=True)
    )

    data_real_por_item = map_real_finalization_dates(list(qs))
    items_faltantes = []
    for item in qs:
        if item.id in ids_inspecionados:
            continue
        item.data_finalizacao_real = data_real_por_item.get(item.id)
        if not item.data_finalizacao_real:
            continue
        if item.data_finalizacao_real < inicio_dt or item.data_finalizacao_real > fim_dt:
            continue
        items_faltantes.append(item)

    items_faltantes.sort(
        key=lambda item: (
            item.data_finalizacao_real,
            item.ordem.ordem if item.ordem else 0,
            item.id,
        )
    )
    return items_faltantes


def serialize_items(items):
    rows = []
    for item in items:
        codigo, descricao = split_peca(item.peca)
        operador = ""
        if item.ordem and item.ordem.operador_final:
            operador = f"{item.ordem.operador_final.matricula} - {item.ordem.operador_final.nome}"

        rows.append(
            {
                "id_peca_ordem": item.id,
                "ordem_id": item.ordem_id,
                "ordem_numero": item.ordem.ordem if item.ordem else "",
                "maquina": item.ordem.maquina.nome if item.ordem and item.ordem.maquina else "",
                "codigo": codigo,
                "descricao": descricao,
                "qtd_boa": item.qtd_boa,
                "data_carga": format_date(item.ordem.data_carga if item.ordem else None),
                "data_finalizacao": format_datetime(
                    getattr(item, "data_finalizacao_real", None)
                ),
                "operador": operador,
                "obs_operador": item.ordem.obs_operador if item.ordem else "",
            }
        )
    return rows


def print_rows(rows):
    if not rows:
        print("Nenhuma ordem encontrada no período informado.")
        return

    header = (
        f"{'ORDEM':>8}  {'MAQUINA':<14}  {'CODIGO':<20}  {'QTD':>8}  "
        f"{'FINALIZACAO':<16}  {'DATA CARGA':<10}  OPERADOR"
    )
    print(header)
    print("-" * len(header))

    for row in rows:
        print(
            f"{str(row['ordem_numero'] or row['ordem_id']):>8}  "
            f"{row['maquina'][:14]:<14}  "
            f"{row['codigo'][:20]:<20}  "
            f"{row['qtd_boa']:>8}  "
            f"{row['data_finalizacao']:<16}  "
            f"{row['data_carga']:<10}  "
            f"{row['operador']}"
        )

    print("")
    print(f"Total de finalizações encontradas: {len(rows)}")


def write_csv(rows, path):
    fieldnames = [
        "id_peca_ordem",
        "ordem_id",
        "ordem_numero",
        "maquina",
        "codigo",
        "descricao",
        "qtd_boa",
        "data_carga",
        "data_finalizacao",
        "operador",
        "obs_operador",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_missing_inspections(items):
    ids_candidatos = [item.id for item in items]
    if not ids_candidatos:
        return 0

    with transaction.atomic():
        ids_ja_inspecionados = set(
            Inspecao.objects.select_for_update()
            .filter(pecas_ordem_montagem_id__in=ids_candidatos)
            .values_list("pecas_ordem_montagem_id", flat=True)
        )

        itens_para_criar = [
            item for item in items if item.id not in ids_ja_inspecionados
        ]

        if not itens_para_criar:
            return 0

        criadas = 0
        for item in itens_para_criar:
            inspecao = Inspecao.objects.create(pecas_ordem_montagem=item)
            if getattr(item, "data_finalizacao_real", None):
                Inspecao.objects.filter(pk=inspecao.pk).update(
                    data_inspecao=item.data_finalizacao_real
                )
            criadas += 1

        return criadas


def main():
    args = parse_args()
    data_inicio = parse_date(args.inicio, "Data inicial")
    data_fim = parse_date(args.fim, "Data final")

    if data_inicio > data_fim:
        raise SystemExit("Intervalo inválido: a data inicial é maior que a data final.")

    items = fetch_missing_items(data_inicio, data_fim)
    rows = serialize_items(items)
    print_rows(rows)

    if args.csv_path:
        write_csv(rows, args.csv_path)
        print(f"CSV gerado em: {args.csv_path}")

    if not args.aplicar:
        print("Dry-run: nenhuma inspeção criada. Use --aplicar para persistir.")
        return

    criadas = create_missing_inspections(items)
    print(f"Inspeções criadas: {criadas}")


if __name__ == "__main__":
    main()
