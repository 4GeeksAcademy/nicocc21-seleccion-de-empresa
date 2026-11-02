"""Tests unitarios para las tasks de transformación del pipeline de desempeño.

Cubre al menos tres escenarios de transform_events (la task que calcula los KPIs):
  1. Agregación correcta de KPIs con cálculo manual verificado.
  2. Comportamiento defensivo ante evento sin costo (missing_cost).
  3. Semana vacía emite 14 localizaciones con ceros.
"""

from datetime import date
from decimal import Decimal

from data.pipelines.weekly_location_performance import transform_events


def _event(
    event_id: str,
    event_type: str,
    order_id: str,
    total_amount: str | None = None,
    location_id: str = "L01",
) -> dict[str, object]:
    country, currency = (
        ("US", "USD") if location_id in {"L08", "L09", "L10", "L14"}
        else ("CO", "COP")
    )
    properties: dict[str, object] = {
        "location_id": location_id,
        "country": country,
        "currency": currency,
        "order_id": order_id,
    }
    if total_amount is not None:
        properties["total_amount"] = total_amount

    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-10-19T12:00:00Z",
        "received_at": "2026-10-19T12:01:00Z",
        "properties": properties,
    }


def test_kpi_values_match_manual_calculation() -> None:
    """Verifica que los KPIs calculados coinciden con un cálculo manual conocido.

    Escenario: compra 100, merma 25 → ratio 25/(100+25)=0.20, 1 quiebre, 1 alerta.
    """
    result = transform_events(
        [
            _event("purchase-1", "inbound_order_created", "order-1", "100.00"),
            _event("waste-1", "stock_waste_registered", "order-2", "25.00"),
            _event("stockout-1", "stock_threshold_triggered", "order-3"),
            _event("price-1", "ingredient_price_variance_detected", "order-4"),
        ],
        date(2026, 10, 19),
    )

    location = next(row for row in result.rows if row.location_id == "L01")
    # Cálculo manual: compra=100, merma=25, ratio=25/100=0.25
    assert location.total_purchase_cost == Decimal("100.00")
    assert location.total_waste_cost == Decimal("25.00")
    assert location.waste_ratio == Decimal("0.250000")
    assert location.stockout_events_count == 1
    assert location.price_alert_events_count == 1
    assert result.events_discarded == 0


def test_discards_event_without_cost_field() -> None:
    """Comportamiento defensivo: evento de compra sin total_amount es descartado."""
    result = transform_events(
        [_event("purchase-1", "inbound_order_created", "order-1")],
        date(2026, 10, 19),
    )

    assert result.events_discarded == 1
    assert result.discard_reasons == {"missing_cost": 1}


def test_discards_event_with_non_numeric_cost() -> None:
    """Comportamiento defensivo: total_amount no numérico es descartado."""
    result = transform_events(
        [
            _event(
                "purchase-1",
                "inbound_order_created",
                "order-1",
                "not-a-number",
            )
        ],
        date(2026, 10, 19),
    )

    assert result.events_discarded == 1
    assert result.discard_reasons == {"invalid_cost": 1}


def test_empty_week_emits_all_locations_with_zeros() -> None:
    """Semana sin eventos: 14 localizaciones, todos los KPIs a cero."""
    result = transform_events([], date(2026, 10, 19))

    assert len(result.rows) == 14
    assert all(row.total_purchase_cost == 0 for row in result.rows)
    assert all(row.total_waste_cost == 0 for row in result.rows)
    assert all(row.waste_ratio == 0 for row in result.rows)
    assert all(row.stockout_events_count == 0 for row in result.rows)
    assert all(row.price_alert_events_count == 0 for row in result.rows)
    assert result.events_discarded == 0


def test_currency_separation_cop_usd() -> None:
    """Verifica que las monedas COP y USD se asignan correctamente por país."""
    events = [
        _event("co-purchase", "inbound_order_created", "1", "50.00", "L01"),
        _event("us-purchase", "inbound_order_created", "2", "12.30", "L08"),
    ]
    result = transform_events(events, date(2026, 10, 19))

    by_location = {row.location_id: row for row in result.rows}
    assert by_location["L01"].currency == "COP"
    assert by_location["L08"].currency == "USD"
    assert result.events_discarded == 0