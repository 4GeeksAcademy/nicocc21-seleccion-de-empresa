"""Entry point CLI del pipeline diario de KPIs de telemetría."""

from __future__ import annotations

import argparse
from datetime import date

from services.telemetry.daily_kpi import compute_and_persist_kpis


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcular KPIs diarios de telemetría")
    parser.add_argument("--target-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    results = compute_and_persist_kpis(args.target_date.isoformat())
    for metric_name, rows in results.items():
        print(f"{metric_name}: {len(rows)} filas")


if __name__ == "__main__":
    main()