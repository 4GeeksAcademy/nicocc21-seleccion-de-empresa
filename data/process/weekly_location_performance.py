from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping


EVENT_TYPES = {
    "inbound_order_created",
    "stock_waste_registered",
    "stock_threshold_triggered",
    "ingredient_price_variance_detected",
}
RATIO_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class WeeklyLocationPerformance:
    location_id: str
    country: str
    week_start: date
    total_purchase_cost: Decimal
    total_waste_cost: Decimal
    waste_ratio: Decimal
    stockout_events_count: int
    price_alert_events_count: int
    currency: str


@dataclass(frozen=True)
class AggregationResult:
    rows: tuple[WeeklyLocationPerformance, ...]
    events_read: int
    events_discarded: int
    discard_reasons: Mapping[str, int]
    source_max_received_at: datetime | None


def week_bounds(week_start: date) -> tuple[datetime, datetime]:
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _as_utc(value: object) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("invalid_timestamp")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _amount(properties: Mapping[str, object]) -> Decimal:
    value = properties.get("total_amount")
    if not isinstance(value, (str, int, Decimal)):
        raise ValueError("missing_cost")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid_cost") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_cost")
    return amount


def aggregate_weekly_location_performance(
    events: Iterable[Mapping[str, object]],
    locations: Iterable[Mapping[str, object]],
    week_start: date,
) -> AggregationResult:
    start, end = week_bounds(week_start)
    location_map = {str(item["code"]): item for item in locations}
    totals: dict[str, dict[str, object]] = {
        location_id: {
            "country": str(location["country"]),
            "currency": str(location["currency"]),
            "purchase": Decimal(0),
            "waste": Decimal(0),
            "stockouts": 0,
            "price_alerts": 0,
        }
        for location_id, location in location_map.items()
    }
    discard_reasons: dict[str, int] = {}
    seen_events: set[str] = set()
    seen_orders: set[tuple[str, str]] = set()
    events_read = 0
    latest_received: datetime | None = None

    def discard(reason: str) -> None:
        discard_reasons[reason] = discard_reasons.get(reason, 0) + 1

    for event in events:
        event_type = event.get("event_type")
        if event_type not in EVENT_TYPES:
            continue
        try:
            timestamp = _as_utc(event.get("timestamp"))
        except (TypeError, ValueError):
            discard("invalid_timestamp")
            continue
        if not start <= timestamp < end:
            continue

        events_read += 1
        try:
            received_at = _as_utc(event.get("received_at"))
            latest_received = max(latest_received, received_at) if latest_received else received_at
        except (TypeError, ValueError):
            pass

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            discard("missing_event_id")
            continue
        if event_id in seen_events:
            discard("duplicate_event")
            continue
        seen_events.add(event_id)

        properties = event.get("properties")
        if not isinstance(properties, Mapping):
            discard("invalid_properties")
            continue
        location_id = properties.get("location_id")
        location = location_map.get(str(location_id))
        if location is None:
            discard("unknown_location")
            continue
        if (
            properties.get("country") != location["country"]
            or properties.get("currency") != location["currency"]
        ):
            discard("currency_mismatch")
            continue

        order_id = properties.get("order_id")
        if not isinstance(order_id, str) or not order_id:
            discard("missing_order_id")
            continue
        order_key = (str(event_type), order_id)
        if order_key in seen_orders:
            discard("duplicate_order")
            continue
        seen_orders.add(order_key)

        row = totals[str(location_id)]
        if event_type in {"inbound_order_created", "stock_waste_registered"}:
            try:
                amount = _amount(properties)
            except ValueError as exc:
                discard(str(exc))
                continue
            key = "purchase" if event_type == "inbound_order_created" else "waste"
            row[key] = row[key] + amount
        elif event_type == "stock_threshold_triggered":
            row["stockouts"] += 1
        else:
            row["price_alerts"] += 1

    rows = []
    for location_id, values in sorted(totals.items()):
        purchase = values["purchase"]
        waste = values["waste"]
        ratio = (
            (waste / purchase).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)
            if purchase
            else Decimal(0)
        )
        rows.append(
            WeeklyLocationPerformance(
                location_id=location_id,
                country=str(values["country"]),
                week_start=week_start,
                total_purchase_cost=purchase,
                total_waste_cost=waste,
                waste_ratio=ratio,
                stockout_events_count=int(values["stockouts"]),
                price_alert_events_count=int(values["price_alerts"]),
                currency=str(values["currency"]),
            )
        )

    return AggregationResult(
        rows=tuple(rows),
        events_read=events_read,
        events_discarded=sum(discard_reasons.values()),
        discard_reasons=discard_reasons,
        source_max_received_at=latest_received,
    )