from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from data.pipelines.storage import ensure_reporting_tables, get_engine, pipeline_runs


def recover_stale_pipeline_runs(
    now: datetime | None = None,
    stale_after_minutes: int | None = None,
) -> int:
    timeout_minutes = stale_after_minutes
    if timeout_minutes is None:
        timeout_minutes = int(os.getenv("REPORTING_STALE_RUN_MINUTES", "180"))
    if timeout_minutes <= 0:
        raise ValueError("REPORTING_STALE_RUN_MINUTES debe ser positivo")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    cutoff = current_time.astimezone(timezone.utc) - timedelta(minutes=timeout_minutes)

    ensure_reporting_tables()
    with get_engine().begin() as connection:
        result = connection.execute(
            update(pipeline_runs)
            .where(
                pipeline_runs.c.status == "running",
                pipeline_runs.c.started_at < cutoff,
            )
            .values(
                status="failed",
                finished_at=current_time,
                error_message=f"Marked failed after exceeding {timeout_minutes} minutes",
            )
        )
    return result.rowcount or 0
