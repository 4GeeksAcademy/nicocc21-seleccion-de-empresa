#!/usr/bin/env python3
"""Exportar telemetría y lanzar el pipeline diario en un proceso separado."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from services.telemetry.exporter import export_telemetry_csv
from services.telemetry.job_runner import (
    JOB_NAME,
    create_job_run,
    fail_pending_job,
    get_job_run,
    has_completed_for_date,
    has_processing_lock,
    start_job_run,
    update_job_run,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s job_name=%(job_name)s status=%(status)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("nightly_export")


def _log(level: int, status: str, message: str, *, exc_info: bool = False) -> None:
    logger.log(
        level,
        message,
        extra={"job_name": JOB_NAME, "status": status},
        exc_info=exc_info,
    )


def _resolve_target_date() -> date:
    """Retorna TARGET_DATE o ayer UTC."""
    env_date = os.environ.get("TARGET_DATE")
    if not env_date:
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    resolved = date.fromisoformat(env_date)
    if resolved.isoformat() != env_date:
        raise ValueError("TARGET_DATE debe usar el formato YYYY-MM-DD")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Export nocturno de telemetría (DEV-53)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin persistir cambios ni exportar CSV",
    )
    args = parser.parse_args()

    try:
        target_date = _resolve_target_date()
    except ValueError as exc:
        _log(logging.ERROR, "invalid", str(exc))
        raise SystemExit(2) from exc

    _log(logging.INFO, "started", f"Ejecución iniciada para {target_date}")
    if args.dry_run:
        _log(logging.INFO, "dry_run", "Simulación: no se realizaron cambios")
        return

    if has_processing_lock():
        _log(logging.INFO, "blocked", "Omitido: ya existe una ejecución processing")
        return

    run = create_job_run(target_date)
    if run.status == "completed" or has_completed_for_date(target_date):
        _log(logging.INFO, "skipped_duplicate", "Omitido: fecha ya completada")
        return

    if run.status == "processing":
        _log(logging.INFO, "blocked", "Omitido: la fecha ya está processing")
        return

    run = start_job_run(target_date)
    if run is None:
        lock_error = "Otra ejecución tiene el lock processing"
        fail_pending_job(target_date, lock_error)
        _log(logging.INFO, "blocked", lock_error)
        return

    _log(logging.INFO, "processing", f"Lock adquirido para {target_date}")
    try:
        csv_path = export_telemetry_csv(target_date.isoformat())
        _log(logging.INFO, "processing", f"Snapshot disponible: {csv_path}")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "services.telemetry.kpi_pipeline",
                "--target-date",
                target_date.isoformat(),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            _log(logging.INFO, "processing", f"Pipeline: {line}")

        update_job_run(target_date, "completed")
        _log(logging.INFO, "completed", f"Ejecución completada para {target_date}")
    except BaseException as exc:
        error_message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            error_message = f"{error_message}: {exc.stderr.strip()}"
        try:
            current = get_job_run(target_date)
            if current is not None and current.status == "processing":
                update_job_run(target_date, "failed", error_message)
        except Exception:
            _log(logging.ERROR, "failed", "No se pudo persistir el estado failed", exc_info=True)
        _log(logging.ERROR, "failed", error_message, exc_info=True)
        if not isinstance(exc, Exception):
            raise
        raise SystemExit(1) from exc
    finally:
        current = get_job_run(target_date)
        if current is not None and current.status == "processing":
            update_job_run(target_date, "failed", "Ejecución terminó sin estado final")


if __name__ == "__main__":
    main()