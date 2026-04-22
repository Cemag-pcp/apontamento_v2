import argparse
import csv
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apontamento_v2.settings")

import django

django.setup()

from cadastro.models import CarretasExplodidas, Pecas


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Compara os pares codigo | materia_prima entre "
            "cadastro_carretasexplodidas e cadastro_pecas."
        )
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Caminho opcional para exportar o resultado em CSV.",
    )
    return parser.parse_args()


def normalize(value):
    if value is None:
        return ""
    return str(value).strip()


def fetch_carretas_pairs():
    pairs = set()
    queryset = (
        CarretasExplodidas.objects
        .values_list("codigo_peca", "mp_peca")
        .distinct()
    )

    for codigo, mp in queryset:
        codigo_norm = normalize(codigo)
        if not codigo_norm:
            continue
        pairs.add((codigo_norm, normalize(mp)))

    return pairs


def fetch_pecas_pairs():
    pairs = set()
    queryset = (
        Pecas.objects
        .values_list("codigo", "materia_prima")
        .distinct()
    )

    for codigo, materia_prima in queryset:
        codigo_norm = normalize(codigo)
        if not codigo_norm:
            continue
        pairs.add((codigo_norm, normalize(materia_prima)))

    return pairs


def build_missing_rows():
    pairs_carretas = fetch_carretas_pairs()
    pairs_pecas = fetch_pecas_pairs()

    missing = [
        {"codigo": codigo, "materia_prima": materia_prima}
        for codigo, materia_prima in pairs_carretas
        if (codigo, materia_prima) not in pairs_pecas
    ]
    missing.sort(key=lambda row: (row["codigo"], row["materia_prima"]))
    return missing


def print_rows(rows):
    if not rows:
        print("Nenhum par codigo | materia_prima faltante foi encontrado.")
        return

    codigo_width = max(len("CODIGO"), max(len(row["codigo"]) for row in rows))
    mp_width = max(
        len("MATERIA_PRIMA"),
        max(len(row["materia_prima"]) for row in rows),
    )

    header = f"{'CODIGO':<{codigo_width}}  {'MATERIA_PRIMA':<{mp_width}}"
    print(header)
    print("-" * len(header))

    for row in rows:
        print(
            f"{row['codigo']:<{codigo_width}}  "
            f"{row['materia_prima']:<{mp_width}}"
        )

    print()
    print(f"Total de pares faltantes: {len(rows)}")


def export_csv(rows, csv_path):
    path = Path(csv_path).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["codigo", "materia_prima"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV exportado para: {path}")


def main():
    args = parse_args()
    rows = build_missing_rows()
    print_rows(rows)

    if args.csv:
        export_csv(rows, args.csv_path)


if __name__ == "__main__":
    main()
