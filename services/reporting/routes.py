from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlmodel import Session

from data.pipelines.storage import pipeline_runs, weekly_location_performance
from data.pipelines.recovery import recover_stale_pipeline_runs
from data.pipelines.weekly_location_performance import (
    PIPELINE_NAME,
    PipelineAlreadyRunning,
    weekly_location_performance_flow,
)
from data.process.weekly_location_performance import week_bounds
from services.brasaland_api.database import get_db

router = APIRouter(prefix="/reporting", tags=["Reporting"])


class ManualPipelineRun(BaseModel):
    week_start: date | None = None


@router.get("/weekly-location-performance")
def get_weekly_location_performance(
    week_start: date | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    if week_start is not None:
        try:
            week_bounds(week_start)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        week_start = session.exec(
            select(func.max(weekly_location_performance.c.week_start))
        ).one()
    if week_start is None:
        raise HTTPException(status_code=404, detail="WEEKLY_REPORT_NOT_AVAILABLE")

    rows = session.execute(
        select(weekly_location_performance)
        .where(weekly_location_performance.c.week_start == week_start)
        .order_by(weekly_location_performance.c.location_id)
    ).mappings().all()
    return {
        "week_start": week_start.isoformat(),
        "locations": [
            {
                key: row[key]
                for key in (
                    "location_id",
                    "country",
                    "stockout_events_count",
                    "price_alert_events_count",
                    "currency",
                )
            }
            | {
                "total_purchase_cost": float(row["total_purchase_cost"]),
                "total_waste_cost": float(row["total_waste_cost"]),
                "waste_ratio": float(row["waste_ratio"]),
            }
            for row in rows
        ],
    }


@router.get("/pipeline-runs/latest")
def get_latest_pipeline_run(session: Session = Depends(get_db)) -> dict[str, Any]:
    row = session.execute(
        select(pipeline_runs)
        .where(pipeline_runs.c.pipeline_name == PIPELINE_NAME)
        .order_by(pipeline_runs.c.started_at.desc())
        .limit(1)
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="PIPELINE_RUN_NOT_AVAILABLE")
    return dict(row)


@router.post("/pipeline-runs")
def create_pipeline_run(
    payload: ManualPipelineRun | None = Body(default=None),
) -> dict[str, Any]:
    week_start = payload.week_start if payload else None
    recover_stale_pipeline_runs()
    try:
        runs = weekly_location_performance_flow(week_start, trigger="manual")
    except PipelineAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"runs": runs}