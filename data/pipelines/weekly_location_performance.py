from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from prefect import flow, task
from sqlalchemy import insert, text, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.pipelines.storage import (
    ensure_reporting_tables,
    get_engine,
    pipeline_runs,
    weekly_location_performance,
)
from data.process.weekly_location_performance import (
    AggregationResult,
    aggregate_weekly_location_performance,
    week_bounds,
)

_logger = logging.getLogger(__name__)
PIPELINE_NAME = "weekly_location_performance"


class PipelineAlreadyRunning(RuntimeError):
    def __init__(self, week_start: date) -> None:
        super().__init__(f"Pipeline already running for {week_start.isoformat()}")
        self.week_start = week_start


def _closed_week_start(today: date | None = None) -> date:
    current = today or datetime.now(timezone.utc).date()
    this_monday = current - timedelta(days=current.weekday())
    return this_monday - timedelta(days=7)


def _create_run(week_start: date, trigger: str) -> UUID:
    run_id = uuid4()
    try:
        with get_engine().begin() as connection:
            connection.execute(
                insert(pipeline_runs).values(
                    run_id=run_id,
                    pipeline_name=PIPELINE_NAME,
                    trigger=trigger,
                    week_start=week_start,
                    status="running",
                )
            )
    except IntegrityError as exc:
        raise PipelineAlreadyRunning(week_start) from exc
    return run_id


@task(name="extract-telemetry-events", retries=3, retry_delay_seconds=2)
def extract_telemetry_events(week_start: date) -> list[dict[str, object]]:
    start, end = week_bounds(week_start)
    query = """
        SELECT event_id, timestamp, event_type, properties, received_at
        FROM telemetry_events
        WHERE event_type IN (
            'inbound_order_created', 'stock_waste_registered',
            'stock_threshold_triggered', 'ingredient_price_variance_detected'
        )
          AND timestamp >= :start AND timestamp < :end
        ORDER BY timestamp, event_id
    """
    with Session(get_engine()) as session:
        rows = session.execute(text(query), {"start": start, "end": end}).mappings().all()
    return [dict(row) for row in rows]


@task(name="validate-and-aggregate-location-week")
def transform_events(
    events: list[dict[str, object]], week_start: date
) -> AggregationResult:
    locations_path = Path(__file__).resolve().parents[2] / "data" / "locations.json"
    with locations_path.open(encoding="utf-8") as source:
        locations = json.load(source)
    return aggregate_weekly_location_performance(events, locations, week_start)


@task(name="upsert-weekly-location-performance", retries=3, retry_delay_seconds=2)
def load_weekly_performance(result: AggregationResult) -> int:
    rows = [
        {
            "location_id": row.location_id,
            "country": row.country,
            "week_start": row.week_start,
            "total_purchase_cost": row.total_purchase_cost,
            "total_waste_cost": row.total_waste_cost,
            "waste_ratio": row.waste_ratio,
            "stockout_events_count": row.stockout_events_count,
            "price_alert_events_count": row.price_alert_events_count,
            "currency": row.currency,
        }
        for row in result.rows
    ]
    statement = postgres_insert(weekly_location_performance).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[
            weekly_location_performance.c.location_id,
            weekly_location_performance.c.week_start,
        ],
        set_={
            key: getattr(statement.excluded, key)
            for key in (
                "country",
                "total_purchase_cost",
                "total_waste_cost",
                "waste_ratio",
                "stockout_events_count",
                "price_alert_events_count",
                "currency",
            )
        }
        | {"computed_at": datetime.now(timezone.utc)},
    )
    with get_engine().begin() as connection:
        connection.execute(statement)
    return len(rows)


def _finish_run(
    run_id: UUID,
    status: str,
    result: AggregationResult | None = None,
    rows_upserted: int = 0,
    error: str | None = None,
) -> None:
    values: dict[str, object] = {
        "status": status,
        "finished_at": datetime.now(timezone.utc),
        "error_message": error,
    }
    if result is not None:
        values.update(
            events_read=result.events_read,
            events_discarded=result.events_discarded,
            discard_reasons=dict(result.discard_reasons),
            source_max_received_at=result.source_max_received_at,
        )
    values["rows_upserted"] = rows_upserted
    with get_engine().begin() as connection:
        connection.execute(
            update(pipeline_runs).where(pipeline_runs.c.run_id == run_id).values(**values)
        )


def _run_week(week_start: date, trigger: str) -> dict[str, object]:
    run_id = _create_run(week_start, trigger)
    result: AggregationResult | None = None
    rows_upserted = 0
    try:
        events = extract_telemetry_events(week_start)
        result = transform_events(events, week_start)
        rows_upserted = load_weekly_performance(result)
        _finish_run(run_id, "completed", result, rows_upserted)
    except Exception as exc:
        try:
            _finish_run(run_id, "failed", result, rows_upserted, str(exc)[:2000])
        except Exception:
            _logger.exception("No se pudo registrar el fallo de la corrida %s", run_id)
        raise
    return {
        "run_id": str(run_id),
        "week_start": week_start.isoformat(),
        "status": "completed",
        "events_read": result.events_read,
        "events_discarded": result.events_discarded,
        "rows_upserted": rows_upserted,
    }


@flow(name=PIPELINE_NAME, log_prints=False)
def weekly_location_performance_flow(
    week_start: date | None = None,
    trigger: str = "scheduled",
) -> list[dict[str, object]]:
    if trigger not in {"scheduled", "manual"}:
        raise ValueError("trigger must be 'scheduled' or 'manual'")
    ensure_reporting_tables()
    if week_start is not None:
        week_bounds(week_start)
        weeks = [week_start]
    else:
        latest_closed = _closed_week_start()
        weeks = [latest_closed - timedelta(days=7), latest_closed]
    return [_run_week(target_week, trigger) for target_week in weeks]