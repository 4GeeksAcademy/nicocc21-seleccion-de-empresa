"""Modelo ORM de telemetría (SQLModel + Supabase/PostgreSQL).

Sin ``from __future__ import annotations``: SQLModel necesita las anotaciones reales.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryEventRecord(SQLModel, table=True):
    """Evento válido del contrato 1.0.0; ``event_id`` único evita duplicados en reintentos."""

    __tablename__ = "telemetry_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(unique=True, index=True)
    timestamp: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True, nullable=False))
    event_type: str = Field(index=True)
    schema_version: str
    request_id: str = Field(index=True)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    properties: dict[str, Any] = Field(
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    )
    received_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )