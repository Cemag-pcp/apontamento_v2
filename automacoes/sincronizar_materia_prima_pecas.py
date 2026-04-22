import argparse
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")

import django

django.setup()

from django.db import transaction

from cadastro.models import CarretasExplodidas, Pecas


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Sincroniza cadastro_pecas.materia_prima com "
            "cadastro_carretasexplodidas.mp_peca pelo codigo da peca."
        )
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Aplica as alteracoes no banco. Sem esta flag, roda apenas em simulacao.",
    )
    return parser.parse_args()


def normalize(value):
    if value is None:
        return ""
    return str(value).strip()


def build_mp_map_from_carretas():
    mapa = {}
    queryset = (
        CarretasExplodidas.objects
        .values_list("codigo_peca", "mp_peca")
        .distinct()
    )

    for codigo, mp_peca in queryset:
        codigo_norm = normalize(codigo)
        mp_norm = normalize(mp_peca)

        if not codigo_norm or not mp_norm:
            continue

        mapa.setdefault(codigo_norm, set()).add(mp_norm)

    return mapa


def collect_changes():
    mp_por_codigo = build_mp_map_from_carretas()
    pecas = (
        Pecas.objects
        .filter(setor__nome__in=["corte", "serra"])
        .distinct()
        .order_by("codigo", "id")
    )

    atualizacoes = []
    ambiguos = []

    for peca in pecas:
        codigo = normalize(peca.codigo)
        if not codigo:
            continue

        mps_carretas = mp_por_codigo.get(codigo)
        if not mps_carretas:
            continue

        if len(mps_carretas) > 1:
            ambiguos.append(
                {
                    "codigo": codigo,
                    "materia_prima_atual": normalize(peca.materia_prima),
                    "materias_primas_carretas": sorted(mps_carretas),
                }
            )
            continue

        mp_destino = next(iter(mps_carretas))
        mp_atual = normalize(peca.materia_prima)

        if mp_atual == mp_destino:
            continue

        atualizacoes.append(
            {
                "peca": peca,
                "codigo": codigo,
                "antes": mp_atual,
                "depois": mp_destino,
            }
        )

    return atualizacoes, ambiguos


def print_changes(atualizacoes):
    if not atualizacoes:
        print("Nenhuma correcao necessaria em cadastro_pecas.")
        return

    print("Correcoes identificadas:")
    for item in atualizacoes:
        antes = item["antes"] or "(vazio)"
        depois = item["depois"] or "(vazio)"
        print(f"{item['codigo']}: {antes} -> {depois}")


def print_ambiguous(ambiguos):
    if not ambiguos:
        return

    print()
    print("Codigos ignorados por ambiguidade em cadastro_carretasexplodidas:")
    for item in ambiguos:
        opcoes = " | ".join(item["materias_primas_carretas"])
        atual = item["materia_prima_atual"] or "(vazio)"
        print(f"{item['codigo']}: atual={atual} | opcoes={opcoes}")


@transaction.atomic
def apply_changes(atualizacoes):
    for item in atualizacoes:
        peca = item["peca"]
        peca.materia_prima = item["depois"] or None
        peca.save(update_fields=["materia_prima"])


def main():
    args = parse_args()
    atualizacoes, ambiguos = collect_changes()

    print_changes(atualizacoes)
    print_ambiguous(ambiguos)

    print()
    print(f"Total de correcoes: {len(atualizacoes)}")
    print(f"Total de codigos ambiguos ignorados: {len(ambiguos)}")

    if not args.aplicar:
        print()
        print("Simulacao concluida. Use --aplicar para gravar no banco.")
        return

    apply_changes(atualizacoes)

    print()
    print("Atualizacao concluida com sucesso.")


if __name__ == "__main__":
    main()
