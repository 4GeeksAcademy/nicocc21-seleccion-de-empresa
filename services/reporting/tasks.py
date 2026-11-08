from __future__ import annotations

from datetime import date
from typing import Any

from data.pipelines.recovery import recover_stale_pipeline_runs
from data.pipelines.weekly_location_performance import (
    PipelineAlreadyRunning,
    weekly_location_performance_flow,
)
from services.celery_app import MAX_ATTEMPTS, celery_app


@celery_app.task(
    name="reporting.run_weekly_pipeline",
    autoretry_for=(Exception,),
    dont_autoretry_for=(PipelineAlreadyRunning, ValueError),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=False,
    max_retries=MAX_ATTEMPTS - 1,
)
def run_weekly_pipeline(week_start: str | None = None) -> list[dict[str, Any]]:
    recover_stale_pipeline_runs()
    parsed = date.fromisoformat(week_start) if week_start else None
    return weekly_location_performance_flow(parsed, trigger="manual")
