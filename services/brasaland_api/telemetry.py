from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, Field

MAX_BATCH_EVENTS = 20
MAX_BATCH_BYTES = 64 * 1024


class TelemetryEvent(BaseModel):
    """Modelo Pydantic del envelope estándar de telemetría (contrato 1.0.0).

    Todos los campos son obligatorios; null es un valor explícito, no una
    clave opcional. Se reutiliza sin cambios en la Fase 3 (persistencia).
    """

    eventId: str = Field(..., description="UUID único del evento, conservado en reintentos")
    timestamp: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
                           description="ISO 8601 UTC terminado en Z")
    sessionId: str | None = Field(..., description="Sesión pseudónima o null")
    userId: str | None = Field(..., description="ID interno opaco o null si no identificado")
    event_type: str = Field(..., description="Nombre del evento del catálogo")
    schemaVersion: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    requestId: str = Field(..., description="UUID de correlación de la operación")
    properties: dict[str, object] = Field(..., description="Payload específico del evento")


@lru_cache(maxsize=1)
def event_validator() -> Draft202012Validator:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "telemetry"
        / "event-schemas.json"
    )
    with schema_path.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def reject_nonfinite(value: str) -> float:
    raise ValueError("Non-finite JSON number")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def parse_batch(body: bytes) -> object:
    return json.loads(
        body.decode("utf-8"),
        parse_constant=reject_nonfinite,
        parse_float=finite_float,
    )


def valid_batch_size(payload: object) -> int | None:
    if not isinstance(payload, dict) or set(payload) != {"events"}:
        return None
    events = payload["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_BATCH_EVENTS:
        return None
    validator = event_validator()
    if any(not validator.is_valid(event) for event in events):
        return None
    return len(events)