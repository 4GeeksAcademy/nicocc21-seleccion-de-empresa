"""Entry point principal del pipeline de desempeño de negocio.

Uso:
    python data/pipelines/pipeline.py
    python data/pipelines/pipeline.py --week-start 2026-10-19
    python data/pipelines/pipeline.py --trigger scheduled
    python data/pipelines/pipeline.py --week-start 2026-10-19 --validate
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from data.pipelines.recovery import recover_stale_pipeline_runs
from data.pipelines.weekly_location_performance import (
    PIPELINE_NAME,
    PipelineAlreadyRunning,
    weekly_location_performance_flow,
)

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"


def _run_flow(
    week_start: date | None,
    trigger: str,
) -> list[dict[str, object]]:
    """Ejecuta el pipeline con recuperación previa de corridas colgadas."""
    recover_stale_pipeline_runs()
    return weekly_location_performance_flow(week_start=week_start, trigger=trigger)


def _save_validation(
    flow_result: list[dict[str, object]],
    elapsed_seconds: float,
) -> Path:
    """Guarda el resultado del pipeline en data/eval/ para inspección."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = EVAL_DIR / f"pipeline-run-{timestamp}.json"
    payload: dict[str, Any] = {
        "pipeline": PIPELINE_NAME,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "runs": flow_result,
    }
    filename.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return filename


def _print_summary(flow_result: list[dict[str, object]]) -> None:
    """Imprime un resumen legible del resultado del pipeline."""
    total_events = sum(r.get("events_read", 0) for r in flow_result)
    total_discarded = sum(r.get("events_discarded", 0) for r in flow_result)
    total_upserted = sum(r.get("rows_upserted", 0) for r in flow_result)

    print(f"\n{'='*60}")
    print(f"  Pipeline: {PIPELINE_NAME}")
    print(f"  Semanas procesadas: {len(flow_result)}")
    print(f"  Eventos leídos: {total_events}")
    print(f"  Eventos descartados: {total_discarded}")
    print(f"  Filas insertadas/actualizadas: {total_upserted}")
    print(f"{'='*60}\n")

    for run in flow_result:
        status_icon = "✅" if run.get("status") == "completed" else "❌"
        print(
            f"  {status_icon}  Semana {run['week_start']} "
            f"— {run['status']} "
            f"(run_id: {run['run_id']})"
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline de Desempeño de Negocio — Brasaland",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  %(prog)s                          # Últimas 2 semanas cerradas\n"
            "  %(prog)s --week-start 2026-10-19  # Semana específica\n"
            "  %(prog)s --trigger scheduled      # Simula ejecución programada\n"
            "  %(prog)s --week-start 2026-10-19 --validate  # + guarda en data/eval/\n"
        ),
    )
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        help="Lunes de la semana a calcular (formato YYYY-MM-DD)",
    )
    parser.add_argument(
        "--trigger",
        default="manual",
        choices=["scheduled", "manual"],
        help="Tipo de disparo (default: manual)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Guarda el resultado en data/eval/ para validación",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del pipeline. Retorna 0 si es exitoso, 1 si falla."""
    args = _parse_args(argv)

    start_time = time.perf_counter()

    try:
        flow_result = _run_flow(args.week_start, args.trigger)
    except PipelineAlreadyRunning as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error inesperado: {exc}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - start_time
    _print_summary(flow_result)

    if args.validate:
        path = _save_validation(flow_result, elapsed)
        print(f"\n  Validación guardada en: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())