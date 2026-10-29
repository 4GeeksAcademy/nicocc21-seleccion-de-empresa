from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from data.process.weekly_location_performance import (
    aggregate_weekly_location_performance,
    week_bounds,
)


@pytest.fixture
def locations() -> list[dict[str, object]]:
    path = Path(__file__).resolve().parents[1] / "data" / "locations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def event(
    event_id: str,
    event_type: str,
    order_id: str,
    location_id: str = "L01",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    country, currency = ("US", "USD") if location_id in {"L08", "L09", "L10", "L14"} else ("CO", "COP")
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-10-19T12:00:00Z",
        "received_at": "2026-10-19T12:01:00Z",
        "properties": {
            "location_id": location_id,
            "country": country,
            "currency": currency,
            "order_id": order_id,
            **(extra or {}),
        },
    }


def test_aggregates_business_metrics_and_emits_all_locations(
    locations: list[dict[str, object]],
) -> None:
    events = [
        event("purchase-1", "inbound_order_created", "1", extra={"total_amount": "100.00"}),
        event("purchase-2", "inbound_order_created", "2", extra={"total_amount": "50.00"}),
        event("waste-1", "stock_waste_registered", "3", extra={"total_amount": "15.00"}),
        event("stockout-1", "stock_threshold_triggered", "4"),
        event("stockout-2", "stock_threshold_triggered", "5"),
        event("price-1", "ingredient_price_variance_detected", "6"),
        event("us-purchase", "inbound_order_created", "7", "L08", {"total_amount": "12.30"}),
    ]

    result = aggregate_weekly_location_performance(events, locations, date(2026, 10, 19))
    by_location = {row.location_id: row for row in result.rows}

    assert len(result.rows) == 14
    assert by_location["L01"].total_purchase_cost == 150
    assert by_location["L01"].total_waste_cost == 15
    assert by_location["L01"].waste_ratio == Decimal("0.100000")
    assert by_location["L01"].stockout_events_count == 2
    assert by_location["L01"].price_alert_events_count == 1
    assert by_location["L01"].currency == "COP"
    assert by_location["L08"].total_purchase_cost == Decimal("12.30")
    assert by_location["L08"].currency == "USD"
    assert result.events_discarded == 0


def test_deduplicates_event_and_order_ids(locations: list[dict[str, object]]) -> None:
    purchase = event("purchase-1", "inbound_order_created", "1", extra={"total_amount": "30.00"})
    result = aggregate_weekly_location_performance(
        [
            purchase,
            dict(purchase),
            event("purchase-retry", "inbound_order_created", "1", extra={"total_amount": "30.00"}),
        ],
        locations,
        date(2026, 10, 19),
    )

    assert result.rows[0].total_purchase_cost == 30
    assert result.discard_reasons == {"duplicate_event": 1, "duplicate_order": 1}


def test_discards_invalid_cost_and_country_currency_mismatch(
    locations: list[dict[str, object]],
) -> None:
    missing_cost = event("waste-1", "stock_waste_registered", "1")
    mismatched_currency = event(
        "purchase-1", "inbound_order_created", "2", extra={"total_amount": "10.00"}
    )
    mismatched_currency["properties"]["currency"] = "USD"

    result = aggregate_weekly_location_performance(
        [missing_cost, mismatched_currency], locations, date(2026, 10, 19)
    )

    assert result.events_discarded == 2
    assert result.discard_reasons == {"missing_cost": 1, "currency_mismatch": 1}
    assert result.rows[0].total_waste_cost == 0


def test_ratio_is_zero_without_purchase_cost(locations: list[dict[str, object]]) -> None:
    result = aggregate_weekly_location_performance(
        [event("stockout-1", "stock_threshold_triggered", "1")],
        locations,
        date(2026, 10, 19),
    )
    assert result.rows[0].waste_ratio == 0


def test_week_bounds_requires_monday() -> None:
    with pytest.raises(ValueError, match="Monday"):
        week_bounds(date(2026, 10, 20))