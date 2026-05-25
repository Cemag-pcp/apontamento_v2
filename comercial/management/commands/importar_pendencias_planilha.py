import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from comercial.models import PendenciaImportacaoPlanilha


CSV_TO_MODEL_FIELD = {
    "PED_UFPESSOAOP.REGIAO.NOME": "ped_ufpessoaop_regiao_nome",
    "PED_PESSOA.UF.CODIGO": "ped_pessoa_uf_codigo",
    "PED_OBSERVACAO": "ped_observacao",
    "PED_PESSOA.LOCALIDADE.CODIGO": "ped_pessoa_localidade_codigo",
    "PED_CHCRIACAO": "ped_chcriacao",
    "PED_EMISSAO": "ped_emissao",
    "PED_PREVISAOEMISSAODOC": "ped_previsaoemissaodoc",
    "PED_PROGRAMACA": "ped_programaca",
    "PED_CLASSE.NOME": "ped_classe_nome",
    "PED_PESSOA.CODIGO": "ped_pessoa_codigo",
    "PED_RECURSO.CODIGO": "ped_recurso_codigo",
    "PED_RECURSO.NOME": "ped_recurso_nome",
    "PED_RECURSO.CLASSE.NOME": "ped_recurso_classe_nome",
    "PED_NUMEROSERIE": "ped_numeroserie",
    "PED_NUCLEO.CODIGO": "ped_nucleo_codigo",
    "PED_QUANTIDADE": "ped_quantidade",
    "PED_UNITARIO": "ped_unitario",
    "PED_TOTAL": "ped_total",
    "PED_RECURSO.DESCRICAOGENERICA": "ped_recurso_descricaogenerica",
    "PED_REPRESENTA.CODIGO": "ped_representa_codigo",
    "PED_IDNEGOCIACAO": "ped_idnegociacao",
}

UPSERT_KEY_FIELDS = [
    "ped_idnegociacao",
    "ped_chcriacao",
    "ped_recurso_codigo",
    "ped_numeroserie",
]

DATE_FIELDS = {
    "ped_emissao",
    "ped_previsaoemissaodoc",
    "ped_programaca",
}

DECIMAL_FIELDS = {
    "ped_quantidade",
    "ped_unitario",
    "ped_total",
}


class Command(BaseCommand):
    help = "Importa o relatório de pendências para a tabela do comercial com upsert por item de negociação."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Caminho do arquivo CSV")
        parser.add_argument(
            "--encoding",
            default="cp1252",
            help="Codificação do arquivo CSV. Padrão: cp1252",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser()
        encoding = options["encoding"]

        if not csv_path.exists():
            raise CommandError(f"Arquivo não encontrado: {csv_path}")

        created_count = 0
        updated_count = 0

        with csv_path.open("r", encoding=encoding, newline="") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            missing_columns = sorted(set(CSV_TO_MODEL_FIELD) - set(reader.fieldnames or []))
            if missing_columns:
                raise CommandError(
                    "CSV inválido. Colunas ausentes: " + ", ".join(missing_columns)
                )

            with transaction.atomic():
                for row_number, row in enumerate(reader, start=2):
                    payload = self._normalize_row(row, row_number)
                    lookup = {field: payload[field] for field in UPSERT_KEY_FIELDS}
                    defaults = {
                        field: value
                        for field, value in payload.items()
                        if field not in UPSERT_KEY_FIELDS
                    }

                    _, created = PendenciaImportacaoPlanilha.objects.update_or_create(
                        **lookup,
                        defaults=defaults,
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída. Criados: {created_count}. Atualizados: {updated_count}."
            )
        )

    def _normalize_row(self, row, row_number):
        payload = {}
        for csv_column, model_field in CSV_TO_MODEL_FIELD.items():
            raw_value = (row.get(csv_column) or "").strip()

            if model_field in DATE_FIELDS:
                if not raw_value:
                    raise CommandError(
                        f"Linha {row_number}: campo obrigatório vazio {csv_column}."
                    )
                payload[model_field] = datetime.strptime(raw_value, "%d/%m/%Y").date()
                continue

            if model_field in DECIMAL_FIELDS:
                if not raw_value:
                    raise CommandError(
                        f"Linha {row_number}: campo obrigatório vazio {csv_column}."
                    )
                payload[model_field] = Decimal(raw_value.replace(",", "."))
                continue

            payload[model_field] = raw_value

        return payload
