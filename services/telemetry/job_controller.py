"""Control de estados del script nocturno (DEV-53).

Máquina de estados canónica::

    pending → processing → completed
                        ↘ failed

El **lock distribuido** es el propio estado ``processing``:
una segunda instancia que encuentre una fila en ``processing``
para el mismo ``(job_name, target_date)`` aborta silenciosamente.

Las filas ``failed`` se reintentan. Las filas ``processing``
con ``started_at`` anterior a ``stale_after_minutes`` se consideran
huérfanas y se reclamann.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from services.telemetry.job_runner import (
    create_job_run,
    has_processing_lock,
    start_job_run,
    update_job_run,
)

JOB_NAME = "nightly_export"
STALE_AFTER_MINUTES = 60


def claim_job(
    session: Session,
    job_name: str = JOB_NAME,
    target_date: str | None = None,
    stale_after_minutes: int = STALE_AFTER_MINUTES,
) -> Optional[JobRun]:
    """Intenta adquirir el lock para ``(job_name, target_date)``.

    Returns:
        El objeto ``JobRun`` con estado ``processing`` si se adquirió el lock,
        ``None`` si ya está ``completed`` o aún en ``processing`` (no obsoleto).
    """
    resolved_date = date.fromisoformat(
        target_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    )
    existing = create_job_run(resolved_date, job_name)
    if existing.status in {"completed", "processing"} or has_processing_lock(job_name):
        return None
    return start_job_run(resolved_date, job_name)


def complete_job(
    session: Session,
    job_name: str = JOB_NAME,
    target_date: str | None = None,
) -> None:
    """Transita el job a ``completed``."""
    resolved_date = date.fromisoformat(
        target_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    )
    update_job_run(resolved_date, "completed", job_name=job_name)


def fail_job(
    session: Session,
    error_message: str,
    job_name: str = JOB_NAME,
    target_date: str | None = None,
) -> None:
    """Transita el job a ``failed`` con el mensaje de error."""
    resolved_date = date.fromisoformat(
        target_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    )
    update_job_run(resolved_date, "failed", error_message, job_name=job_name)