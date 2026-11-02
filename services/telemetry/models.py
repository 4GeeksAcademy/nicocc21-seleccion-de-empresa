"""Modelos ORM para el script nocturno de telemetría (DEV-53).

Tablas:
- ``job_runs`` — control de ejecuciones (lock distribuido + idempotencia).
- ``daily_kpi`` — métricas diarias materializadas del pipeline ETL.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import CheckConstraint, Column, DateTime, Index, JSON, UniqueConstraint, text
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# job_runs — control de ejecuciones nocturnas
# ──────────────────────────────────────────────

class JobRun(SQLModel, table=True):
    """Registro de una ejecución del script nocturno.

    Estados: pending → processing → completed | failed.
    La tupla (job_name, target_date) es única: el lock distribuido
    es el propio estado `processing`. Una segunda instancia que
    encuentre una fila en `processing` aborta silenciosamente.
    """

    __tablename__ = "job_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_name: str = Field(max_length=64, index=True)
    target_date: date
    status: str = Field(max_length=16, default="pending", index=True)  # pending|processing|completed|failed
    started_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True, default=None)
    )
    finished_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True, default=None)
    )
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("job_name", "target_date", name="uq_job_runs_job_date"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_job_runs_status",
        ),
        Index(
            "uq_job_runs_one_processing",
            "job_name",
            unique=True,
            postgresql_where=text("status = 'processing'"),
            sqlite_where=text("status = 'processing'"),
        ),
    )


# ──────────────────────────────────────────────
# daily_kpi — métricas diarias materializadas
# ──────────────────────────────────────────────

class DailyKPI(SQLModel, table=True):
    """Métricas operacionales diarias desde telemetry_events.

    Cada fila corresponde a un día y una métrica; se usa UPSERT
    por (target_date, metric_name) para idempotencia.
    """

    __tablename__ = "daily_kpi"

    id: Optional[int] = Field(default=None, primary_key=True)
    target_date: str = Field(max_length=10, index=True)  # YYYY-MM-DD
    metric_name: str = Field(max_length=64)  # events_per_day, error_rate_by_type, etc.
    metric_value: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    computed_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    __table_args__ = (
        UniqueConstraint("target_date", "metric_name", name="uq_daily_kpi_date_metric"),
    )