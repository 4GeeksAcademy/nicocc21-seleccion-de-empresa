
"""Router de telemetría — recepción y persistencia de eventos.

``POST /telemetry/events`` valida el lote contra el contrato 1.0.0,
persiste en la tabla ``telemetry_events`` (Supabase/PostgreSQL) y
retorna el número de eventos aceptados/persistidos.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from sqlmodel import Session, SQLModel

from services.brasaland_api.cache import cached
from services.brasaland_api.database import engine
from services.brasaland_api.telemetry import (
    MAX_BATCH_BYTES,
    TelemetryEvent,
    parse_batch,
    valid_batch_size,
)
from services.brasaland_api.telemetry_models import TelemetryEventRecord
from services.telemetry.analysis import (
    api_latency_summary,
    auth_failure_rate,
    error_rate_by_type,
    events_per_day,
)

_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


def _parse_timestamp(raw: str) -> datetime:
    """Convierte el timestamp ISO del evento (terminado en Z) a datetime con timezone."""
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


def _ensure_tables() -> None:
    """Crea la tabla de telemetría en la BD si no existe (idempotente)."""
    SQLModel.metadata.create_all(engine, tables=[TelemetryEventRecord.__table__])


def _persist_events(events: list[dict]) -> int:
    """Síncrona: persiste eventos en Supabase dentro de una sesión SQLModel.

    Se ejecuta en un thread pool separado para no bloquear el event loop.
    Si un evento ya existe (event_id duplicado) se ignora silenciosamente.
    """
    persisted = 0
    _ensure_tables()
    with Session(engine) as session:
        for event in events:
            try:
                record = TelemetryEventRecord(
                    event_id=event["eventId"],
                    timestamp=_parse_timestamp(event["timestamp"]),
                    event_type=event["event_type"],
                    schema_version=event["schemaVersion"],
                    request_id=event["requestId"],
                    session_id=event.get("sessionId"),
                    user_id=event.get("userId"),
                    properties=event.get("properties", {}),
                )
                session.add(record)
                session.commit()
                persisted += 1
            except Exception:
                session.rollback()
                _logger.exception("Error al persistir evento %s", event.get("eventId"))
                # Si falla uno, saltamos al siguiente (no abortamos el lote)
    return persisted


@router.post(
    "/events",
    summary="Validar y persistir un lote de telemetría",
    description=(
        "Valida entre 1 y 20 eventos contra el contrato 1.0.0, "
        "con limite de 64 KiB, y persiste los eventos válidos en Supabase. "
        "Cada evento requiere un eventId único (UUID); si se reintenta un evento "
        "ya existente se ignora silenciosamente."
    ),
    responses={
        400: {"description": "JSON invalido"},
        413: {"description": "Lote superior a 64 KiB"},
        415: {"description": "Se requiere application/json"},
        422: {"description": "Lote o evento incompatible con el contrato"},
    },
)
async def receive_events(request: Request) -> dict[str, int]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(status_code=415, detail="JSON_CONTENT_TYPE_REQUIRED")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BATCH_BYTES:
            raise HTTPException(status_code=413, detail="TELEMETRY_BATCH_TOO_LARGE")
        body.extend(chunk)

    try:
        payload = parse_batch(bytes(body))
    except (ValueError, RecursionError):
        raise HTTPException(status_code=400, detail="INVALID_JSON") from None

    received = valid_batch_size(payload)
    if received is None:
        raise HTTPException(status_code=422, detail="INVALID_TELEMETRY_BATCH")

    events = payload["events"]
    _logger.info("Telemetría recibida: %d eventos — persistiendo...", received)

    loop = asyncio.get_running_loop()
    persisted = await loop.run_in_executor(None, _persist_events, events)

    _logger.info("Telemetría: %d recibidos, %d persistidos", received, persisted)
    return {"received": received, "persisted": persisted}


@router.get(
    "/report",
    summary="Reporte de telemetría con 4 métricas",
    description=(
        "Devuelve 4 métricas: eventos/día, tasa de error por tipo, "
        "percentiles de latencia y tasa de fallo de autenticación. "
        "Por defecto analiza los últimos 7 días. Cacheado 60 segundos."
    ),
    responses={
        200: {"description": "Reporte de telemetría"},
    },
)
@cached(ttl_seconds=60, skip_args={"request"})
async def telemetry_report(
    request: Request,
    start_date: datetime | None = Query(
        None,
        description="Inicio del período (ISO 8601). Por defecto: now - 7 días UTC.",
    ),
    end_date: datetime | None = Query(
        None,
        description="Fin del período (ISO 8601). Por defecto: now UTC.",
    ),
) -> dict:
    """Reporte de telemetría con 4 métricas.

    El endpoint resuelve el período una sola vez y lo pasa a cada función
    de análisis, evitando ventanas inconsistentes entre métricas.
    """
    end = end_date.replace(tzinfo=timezone.utc) if end_date else datetime.now(timezone.utc)
    start = start_date.replace(tzinfo=timezone.utc) if start_date else end - timedelta(days=7)

    return {
        "period": {
            "from": start.isoformat(),
            "to": end.isoformat(),
        },
        "metrics": {
            "events_per_day": events_per_day(start, end),
            "error_rate_by_type": error_rate_by_type(start, end),
            "api_latency_summary": api_latency_summary(start, end),
            "auth_failure_rate": auth_failure_rate(start, end),
        },
    }