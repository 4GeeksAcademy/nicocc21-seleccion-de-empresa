"""Cómputo y persistencia de KPIs diarios de telemetría (DEV-53).

Reutiliza las 4 métricas existentes de ``services.telemetry.analysis``
y las persiste en la tabla ``daily_kpi`` con UPSERT para idempotencia.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from services.brasaland_api.database import engine
from services.telemetry.analysis import (
    api_latency_summary,
    auth_failure_rate,
    error_rate_by_type,
    events_per_day,
)
from services.telemetry.models import DailyKPI

METRIC_FUNCTIONS: dict[str, callable] = {
    "events_per_day": events_per_day,
    "error_rate_by_type": error_rate_by_type,
    "api_latency_summary": api_latency_summary,
    "auth_failure_rate": auth_failure_rate,
}


def compute_and_persist_kpis(target_date: str) -> dict[str, list[dict[str, Any]]]:
    """Calcula las 4 métricas para ``target_date`` y las persiste en ``daily_kpi``.

    Args:
        target_date: Fecha ISO ``YYYY-MM-DD`` en UTC.

    Returns:
        Dict con nombre de métrica → lista de resultados (para logging/informe).
    """
    start_dt = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)  # semi-open [start, end)

    results: dict[str, list[dict[str, Any]]] = {}
    upsert_sql = text("""
        INSERT INTO daily_kpi (target_date, metric_name, metric_value, computed_at)
        VALUES (:target_date, :metric_name, :metric_value, :computed_at)
        ON CONFLICT (target_date, metric_name) DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            computed_at = EXCLUDED.computed_at
    """)

    with Session(engine) as session:
        for name, func in METRIC_FUNCTIONS.items():
            data = func(start_dt, end_dt)
            results[name] = data
            session.execute(
                upsert_sql,
                {
                    "target_date": target_date,
                    "metric_name": name,
                    "metric_value": data,
                    "computed_at": datetime.now(timezone.utc),
                },
            )
        session.commit()

    return results