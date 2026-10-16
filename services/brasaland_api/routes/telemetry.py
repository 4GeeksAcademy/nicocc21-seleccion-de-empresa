from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from services.brasaland_api.telemetry import (
    MAX_BATCH_BYTES,
    TelemetryEvent,
    parse_batch,
    valid_batch_size,
)

_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post(
    "/events",
    summary="Validar un lote de telemetria sin persistencia",
    description=(
        "Stub: valida entre 1 y 20 eventos contra el contrato 1.0.0, "
        "con limite de 64 KiB. No almacena eventos ni acredita su autenticidad."
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
    _logger.info("Telemetría recibida: %d eventos", received)
    for event in events:
        _logger.info("  → %s | %s", event["event_type"], event["eventId"])

    return {"received": received}