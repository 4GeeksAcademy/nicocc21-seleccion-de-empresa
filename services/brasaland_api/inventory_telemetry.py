from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from statistics import median
from uuid import UUID, uuid4

from fastapi import Request

from services.brasaland_api.inventory_models import Ingredient
from services.brasaland_api.telemetry import event_validator


@dataclass(frozen=True)
class EventContext:
    user_id: str | None
    request_id: str
    session_id: str | None = None
    workflow_id: str | None = None


def valid_uuid(value: str | None) -> str | None:
    try:
        return str(UUID(value)) if value else None
    except ValueError:
        return None


def event_context(request: Request | None, user_id: str | None) -> EventContext:
    headers = request.headers if request else {}
    return EventContext(
        user_id=user_id,
        request_id=valid_uuid(headers.get("x-request-id")) or str(uuid4()),
        session_id=valid_uuid(headers.get("x-telemetry-session-id")),
        workflow_id=valid_uuid(headers.get("x-workflow-id")),
    )


@lru_cache(maxsize=1)
def locations() -> list[dict[str, object]]:
    path = Path(__file__).resolve().parents[2] / "data" / "locations.json"
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def location_for(location_id: int) -> dict[str, object]:
    return next(location for location in locations() if location["id"] == location_id)


def canonical_unit(unit: str) -> str | None:
    return {"kg": "kg", "und": "unit", "unit": "unit", "L": "liter", "liter": "liter"}.get(unit)


def inventory_base(ingredient: Ingredient, location: dict[str, object], quantity: float) -> dict[str, object]:
    return {
        "location_id": location["code"], "country": location["country"],
        "currency": location["currency"], "product_id": str(ingredient.id),
        "product_category": ingredient.category, "quantity": quantity,
        "unit": canonical_unit(ingredient.unit),
    }


def money(amount: Decimal) -> str:
    return format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def price_variance(price: Decimal, previous: list[Decimal], threshold: Decimal) -> dict[str, object] | None:
    positive = [value for value in previous if value.is_finite() and value > 0]
    if len(positive) < 3:
        return None
    reference = Decimal(money(median(positive)))
    if reference <= 0:
        return None
    variance = Decimal(100) * (price - reference) / reference
    if abs(variance) <= threshold:
        return None
    return {
        "unit_price": money(price), "reference_price": money(reference),
        "variance_pct": float(variance), "threshold_pct": float(threshold),
    }


def slug(value: str) -> str:
    """Normaliza un string a slug para propiedades de eventos."""
    return value.lower().replace(" ", "_").replace("-", "_")


def route_template(path: str) -> str:
    """Convierte una URL real en route_template parametrizada."""
    parts = path.strip("/").split("/")
    result: list[str] = []
    for part in parts:
        if part.isdecimal():
            result.append("{id}")
        elif part.isdigit():
            result.append("{id}")
        else:
            result.append(part)
    return "/" + "/".join(result) if result else "/"


def make_event(event_type: str, properties: dict[str, object], context: EventContext, occurred_at: datetime | None = None) -> dict[str, object]:
    timestamp = occurred_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    event: dict[str, object] = {
        "eventId": str(uuid4()), "timestamp": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sessionId": context.session_id, "userId": context.user_id,
        "event_type": event_type, "schemaVersion": "1.0.0", "requestId": context.request_id,
        "properties": properties,
    }
    event_validator().validate(event)
    return event


def workflow_completed(context: EventContext, workflow_type: str, entity_id: int, occurred_at: datetime) -> list[dict[str, object]]:
    if not context.workflow_id:
        return []
    return [make_event("workflow_completed", {
        "workflow_id": context.workflow_id, "workflow_type": workflow_type, "entity_id": str(entity_id),
    }, context, occurred_at)]