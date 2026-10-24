from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from services.brasaland_api.database import get_db
from services.brasaland_api.inventory_models import TelemetryEventRecord
from services.brasaland_api.telemetry import (
    MAX_BATCH_BYTES,
    MAX_BATCH_EVENTS,
    TelemetryEvent,
    event_validator,
    parse_batch,
)

_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post(
    "/events",
    summary="Validar y almacenar un lote de telemetria",
    description=(
        "Valida individualmente hasta 20 eventos contra el contrato 1.0.0 y "
        "persiste los validos en una sola transaccion. Limite de 64 KiB."
    ),
    responses={
        400: {"description": "JSON invalido"},
        413: {"description": "Lote superior a 64 KiB"},
        415: {"description": "Se requiere application/json"},
        422: {"description": "Lote o evento incompatible con el contrato"},
    },
)
async def receive_events(request: Request, session: Session = Depends(get_db)) -> dict[str, int]:
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

    if (
        not isinstance(payload, dict)
        or set(payload) != {"events"}
        or not isinstance(payload["events"], list)
        or len(payload["events"]) > MAX_BATCH_EVENTS
    ):
        raise HTTPException(status_code=422, detail="INVALID_TELEMETRY_BATCH")

    events = payload["events"]
    records: list[TelemetryEventRecord] = []
    rejected = 0
    validator = event_validator()
    for raw_event in events:
        try:
            if not validator.is_valid(raw_event):
                raise ValueError("Evento incompatible con el esquema")
            event = TelemetryEvent.model_validate(raw_event)
        except (ValidationError, TypeError, ValueError):
            rejected += 1
            continue

        records.append(
            TelemetryEventRecord(
                event_id=event.eventId,
                timestamp=datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")),
                session_id=event.sessionId,
                user_id=event.userId,
                event_type=event.event_type,
                schema_version=event.schemaVersion,
                request_id=event.requestId,
                service="brasaland-api",
                tags=event.properties,
            )
        )

    if records:
        try:
            session.execute(insert(TelemetryEventRecord), [record.model_dump() for record in records])
            session.commit()
        except Exception:
            session.rollback()
            _logger.exception("No se pudo persistir el lote de telemetría")
            raise HTTPException(status_code=503, detail="TELEMETRY_STORAGE_UNAVAILABLE") from None

    _logger.info(
        "Lote de telemetría procesado: recibidos=%d almacenados=%d rechazados=%d",
        len(events), len(records), rejected,
    )
    return {"received": len(events), "stored": len(records), "rejected": rejected}