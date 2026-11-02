"""Modelo ORM de telemetría (SQLModel + Supabase/PostgreSQL) — CANÓNICO.

Sin `from __future__ import annotations`: SQLModel necesita las anotaciones reales.
La clase `TelemetryEventRecord` se define AQUÍ y NO debe duplicarse en otro módulo.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryEventRecord(SQLModel, table=True):
    """Evento válido del contrato 1.0.0; `event_id` único evita duplicados en reintentos."""

    __tablename__ = "telemetry_events"
    __table_args__ = (Index("ix_telemetry_events_tags_gin", "tags", postgresql_using="gin"),)

    event_id: str = Field(primary_key=True, max_length=36)
    timestamp: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    event_type: str = Field(index=True)
    schema_version: str
    request_id: str
    service: str
    tags: dict[str, object] = Field(
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    )
