import csv
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")

import django

django.setup()

from django.utils import timezone

from apontamento_corte.models import PecasOrdem

INICIO = timezone.make_aware(datetime(2026, 7, 29, 0, 0, 0))
FIM = timezone.make_aware(datetime(2026, 7, 29, 23, 59, 59))

OUTPUT_PATH = BASE_DIR / "apontamentos_erp_corte_29_07_2026.csv"


def main():
    qs = (
        PecasOrdem.objects.select_related("ordem", "resp_apontamento")
        .exclude(chave_apontamento__isnull=True)
        .exclude(chave_apontamento__exact="")
        .filter(data__gte=INICIO, data__lte=FIM)
        .order_by("data")
    )

    cabecalho = [
        "ID Registro",
        "Número Ordem",
        "Peça",
        "Qtd Planejada",
        "Qtd Boa",
        "Qtd Morta",
        "Data",
        "Data/Hora Apontamento ERP",
        "Chave Apontamento ERP",
        "Tipo Apontamento",
        "Responsável",
        "Apontado",
    ]

    total = qs.count()
    print(f"Exportando {total} registros...")

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(cabecalho)

        for po in qs:
            ordem = po.ordem
            resp = po.resp_apontamento
            data = (
                timezone.localtime(po.data).strftime("%d/%m/%Y %H:%M:%S")
                if po.data
                else ""
            )
            data_apontamento = (
                timezone.localtime(po.data_apontamento).strftime("%d/%m/%Y %H:%M:%S")
                if po.data_apontamento
                else ""
            )

            writer.writerow([
                po.id,
                ordem.ordem if ordem else "",
                po.peca,
                po.qtd_planejada,
                po.qtd_boa,
                po.qtd_morta,
                data,
                data_apontamento,
                po.chave_apontamento,
                po.tipo_apontamento or "",
                resp.get_full_name() if resp else "",
                "Sim" if po.apontado else "Não",
            ])

    print(f"CSV exportado com sucesso: {OUTPUT_PATH}")
    print(f"Total de registros: {total}")


if __name__ == "__main__":
    main()
