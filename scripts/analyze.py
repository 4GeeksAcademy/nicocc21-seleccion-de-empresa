#!/usr/bin/env python3
"""Analizador de incidencias CSV para Brasaland.

Uso:
    python3 scripts/analyze.py scripts/incidents-BRASALAND.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api.incidents_core import (  # noqa: E402
    IncidentsValidationError,
    analyze_rows,
    load_rows_from_path,
    summary_to_csv_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analiza un CSV de incidencias y genera un resumen de metricas."
    )
    parser.add_argument("csv_path", help="Ruta al archivo CSV de incidencias")
    return parser.parse_args()


def print_block(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def print_summary(summary: dict[str, Any]) -> None:
    print_block("RESUMEN DE ANALISIS DE INCIDENCIAS")
    print(f"{'Procesados':40} {summary['total_processed']:>10}")
    print(f"{'Validos':40} {summary['total_valid']:>10}")
    print(f"{'Invalidos':40} {summary['total_invalid']:>10}")

    print_block("INVALIDOS POR TIPO")
    if summary["invalid_reasons"]:
        for reason, count in summary["invalid_reasons"].items():
            print(f"{reason:40} {count:>10}")
    else:
        print("Sin registros invalidos")

    print_block("TOTALIZACION POR CATEGORIA (SOLO VALIDOS)")
    for category, count in summary["by_category"].items():
        print(f"{category:40} {count:>10}")

    print_block("TOTALIZACION POR ESTADO (SOLO VALIDOS)")
    for state, count in summary["by_state"].items():
        print(f"{state:40} {count:>10}")

    print_block("SATISFACCION EN CASOS CERRADOS")
    print(f"{'Cerrados con satisfaccion':40} {summary['closed_with_score']:>10}")
    print(
        f"{'Indice de satisfaccion medio':40} "
        f"{summary['avg_satisfaction_closed_with_score']:>10}"
    )


def export_results(summary: dict[str, Any], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as csvfile:
        csvfile.write(summary_to_csv_text(summary))


def prompt_export() -> bool:
    while True:
        choice = input("\nDeseas exportar los resultados a CSV? [s / n]: ").strip().lower()
        if choice in {"s", "n"}:
            return choice == "s"
        print("Respuesta invalida. Escribe 's' o 'n'.")


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path)

    try:
        rows = load_rows_from_path(csv_path)
    except (FileNotFoundError, IncidentsValidationError) as error:
        print(f"Error: {error}")
        return 1

    summary = analyze_rows(rows)
    print_summary(summary)

    if prompt_export():
        output_path = Path("results.csv")
        export_results(summary, output_path)
        print(f"\nExportacion completada: {output_path.resolve()}")
    else:
        print("\nNo se exportaron resultados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
