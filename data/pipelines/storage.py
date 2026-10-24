from __future__ import annotations

import os
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func


metadata = MetaData()

weekly_location_performance = Table(
    "weekly_location_performance",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid4),
    Column("location_id", String, nullable=False),
    Column("country", String, nullable=False),
    Column("week_start", Date, nullable=False),
    Column("total_purchase_cost", Numeric, nullable=False, server_default="0"),
    Column("total_waste_cost", Numeric, nullable=False, server_default="0"),
    Column("waste_ratio", Numeric, nullable=False, server_default="0"),
    Column("stockout_events_count", Integer, nullable=False, server_default="0"),
    Column("price_alert_events_count", Integer, nullable=False, server_default="0"),
    Column("currency", String, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("location_id", "week_start", name="uq_weekly_location_performance"),
    schema="reporting",
)

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("run_id", Uuid(as_uuid=True), primary_key=True, default=uuid4),
    Column("pipeline_name", String, nullable=False),
    Column("trigger", String, nullable=False),
    Column("week_start", Date, nullable=False),
    Column("status", String, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("finished_at", DateTime(timezone=True)),
    Column("events_read", Integer, nullable=False, server_default="0"),
    Column("events_discarded", Integer, nullable=False, server_default="0"),
    Column("discard_reasons", JSON().with_variant(JSONB(), "postgresql"), nullable=False, server_default="{}"),
    Column("rows_upserted", Integer, nullable=False, server_default="0"),
    Column("source_max_received_at", DateTime(timezone=True)),
    Column("error_message", Text),
    schema="reporting",
)
Index(
    "uq_reporting_pipeline_runs_active",
    pipeline_runs.c.pipeline_name,
    pipeline_runs.c.week_start,
    unique=True,
    postgresql_where=text("status = 'running'"),
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL no está definida")
    return create_engine(database_url, pool_pre_ping=True)


def ensure_reporting_tables(engine: Engine | None = None) -> None:
    active_engine = engine or get_engine()
    with active_engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS reporting"))
        metadata.create_all(connection)