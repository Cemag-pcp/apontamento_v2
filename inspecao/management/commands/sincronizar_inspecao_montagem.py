from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apontamento_montagem.models import ConjuntosInspecionados, PecasOrdem
from inspecao.models import Inspecao


def normalizar_codigo(valor):
    codigo = str(valor or "").strip().replace(" ", "")
    if codigo.endswith(".0"):
        codigo = codigo[:-2]
    return codigo.upper()


def chave_codigo(valor):
    return normalizar_codigo(valor).lstrip("0")


def extrair_codigo_peca(peca_nome):
    texto = str(peca_nome or "").strip()
    if " - " in texto:
        return texto.split(" - ", maxsplit=1)[0].strip()
    if "-" in texto:
        return texto.split("-", maxsplit=1)[0].strip()
    return texto


class Command(BaseCommand):
    help = (
        "Sincroniza inspeções de montagem não criadas por falha de tratamento de string. "
        "Por padrão, busca de hoje 00:00:00 até agora e roda em dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inicio",
            type=str,
            help="Data/hora inicial (ISO), ex: 2026-02-03T00:00:00",
        )
        parser.add_argument(
            "--fim",
            type=str,
            help="Data/hora final (ISO), ex: 2026-02-03T16:30:00",
        )
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Aplica no banco. Sem esta flag, executa apenas simulação.",
        )

    def _parse_dt(self, valor, default_dt):
        if not valor:
            return default_dt
        dt = parse_datetime(valor)
        if not dt:
            raise ValueError(f"Data/hora inválida: {valor}")
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def handle(self, *args, **options):
        agora = timezone.now()
        hoje_inicio = timezone.make_aware(
            datetime.combine(timezone.localdate(), time.min),
            timezone.get_current_timezone(),
        )

        try:
            inicio = self._parse_dt(options.get("inicio"), hoje_inicio)
            fim = self._parse_dt(options.get("fim"), agora)
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        if inicio > fim:
            self.stderr.write(self.style.ERROR("Intervalo inválido: início maior que fim."))
            return

        pecas_qs = (
            PecasOrdem.objects.select_related("ordem", "ordem__maquina", "processo_ordem")
            .filter(
                data__gte=inicio,
                data__lte=fim,
                qtd_boa__gt=0,
                ordem__grupo_maquina="montagem",
                processo_ordem__status="finalizada",
            )
            .order_by("id")
        )

        pecas = list(pecas_qs)
        if not pecas:
            self.stdout.write("Nenhum apontamento de montagem encontrado no período.")
            return

        ids_pecas = [p.id for p in pecas]
        ids_ja_inspecionadas = set(
            Inspecao.objects.filter(pecas_ordem_montagem_id__in=ids_pecas).values_list(
                "pecas_ordem_montagem_id", flat=True
            )
        )

        codigos_cadastro = set(
            chave_codigo(codigo)
            for codigo in ConjuntosInspecionados.objects.values_list("codigo", flat=True)
        )

        criar = []
        elegiveis = 0

        for peca in pecas:
            if peca.id in ids_ja_inspecionadas:
                continue

            codigo = extrair_codigo_peca(peca.peca)
            codigo_chave = chave_codigo(codigo)
            maquina_nome = (
                peca.ordem.maquina.nome.strip().lower()
                if peca.ordem and peca.ordem.maquina and peca.ordem.maquina.nome
                else ""
            )

            conjunto_inspecionado = codigo_chave in codigos_cadastro
            serralheria = maquina_nome == "serralheria"

            if conjunto_inspecionado or serralheria:
                elegiveis += 1
                criar.append(Inspecao(pecas_ordem_montagem=peca))

        self.stdout.write(
            f"Período: {inicio.isoformat()} -> {fim.isoformat()} | "
            f"Apontamentos analisados: {len(pecas)} | Elegíveis sem inspeção: {elegiveis}"
        )

        if not options.get("aplicar"):
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run: nenhuma inspeção criada. Use --aplicar para persistir."
                )
            )
            return

        if not criar:
            self.stdout.write("Nada para criar.")
            return

        Inspecao.objects.bulk_create(criar, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Inspeções criadas: {len(criar)}"))
