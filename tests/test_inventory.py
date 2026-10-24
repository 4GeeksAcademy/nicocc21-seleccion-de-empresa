from __future__ import annotations

import pytest
from decimal import Decimal
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlalchemy import Column, MetaData, Table, inspect
from sqlmodel import Session, SQLModel, create_engine, select

from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit
from services.brasaland_api.inventory_telemetry import location_for, price_variance
from services.brasaland_api.inventory_migration import migrate_inventory_telemetry
from services.brasaland_api.telemetry import event_validator
from services.brasaland_api.routes.inventory import (
    create_inbound,
    create_outbound,
    create_product,
    get_product,
    list_orders,
    list_products,
)
from services.brasaland_api.schemas import (
    IngredientCreate,
    IngredientEntryCreate,
    IngredientExitCreate,
)


@pytest.fixture
def inventory_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def product_payload(
    sku: str = "BRS-BEEF-TEST",
    category: str = "meat",
    country: str = "CO",
) -> IngredientCreate:
    return IngredientCreate(
        name="Falda de ternera",
        sku=sku,
        unit="kg",
        category=category,
        country=country,
        stock_minimo=20,
        perecedero=True,
        dias_vida_util=7,
        frecuencia_rotacion_dias=7,
    )


def create_test_product(session: Session, sku: str = "BRS-BEEF-TEST") -> int:
    product = create_product(product_payload(sku=sku), session, {"id": 7})
    return product.id


def test_create_product_starts_with_zero_stock_and_rejects_duplicate_sku(
    inventory_session: Session,
) -> None:
    product = create_product(product_payload(), inventory_session, {"id": 7})

    assert product.current_stock == 0
    assert product.category == "meat"
    assert product.country == "CO"

    with pytest.raises(HTTPException) as error:
        create_product(product_payload(), inventory_session, {"id": 7})

    assert error.value.status_code == 400
    assert error.value.detail == "Ya existe un insumo con el SKU 'BRS-BEEF-TEST'"


def test_inbound_uses_authenticated_user_and_increases_calculated_stock(
    inventory_session: Session,
) -> None:
    product_id = create_test_product(inventory_session)

    entry = create_inbound(
        IngredientEntryCreate(
            ingredient_id=product_id,
            quantity=50,
            supplier_name="Carnes del Valle S.A.",
            location_id=1,
        ),
        inventory_session,
        {"id": 42},
    )

    assert entry.user_uuid == "42"
    assert entry.type == "inbound"
    assert get_product(product_id, inventory_session).current_stock == 50


def test_outbound_decreases_stock_and_rejects_insufficient_quantity(
    inventory_session: Session,
) -> None:
    product_id = create_test_product(inventory_session)
    create_inbound(
        IngredientEntryCreate(
            ingredient_id=product_id,
            quantity=20,
            supplier_name="Carnes del Valle S.A.",
            location_id=1,
        ),
        inventory_session,
        {"id": 42},
    )

    movement = create_outbound(
        IngredientExitCreate(
            ingredient_id=product_id,
            quantity=5,
            reason="consumption",
            location_id=1,
        ),
        inventory_session,
        {"id": 43},
    )

    assert movement.user_uuid == "43"
    assert movement.type == "outbound"
    assert get_product(product_id, inventory_session).current_stock == 15

    with pytest.raises(HTTPException) as error:
        create_outbound(
            IngredientExitCreate(
                ingredient_id=product_id,
                quantity=16,
                reason="waste",
                location_id=1,
            ),
            inventory_session,
            {"id": 43},
        )

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "INSUFFICIENT_STOCK"
    assert "telemetry_events" in error.value.detail


def test_list_products_calculates_stock_and_applies_filters(
    inventory_session: Session,
) -> None:
    meat_id = create_test_product(inventory_session)
    create_product(
        product_payload(sku="BRS-SAUCE-TEST", category="sauce", country="US"),
        inventory_session,
        {"id": 7},
    )
    create_inbound(
        IngredientEntryCreate(
            ingredient_id=meat_id,
            quantity=12,
            supplier_name="Proveedor de prueba",
            location_id=1,
        ),
        inventory_session,
        {"id": 7},
    )

    products = list_products(inventory_session, categoria="meat", pais="CO")

    assert len(products) == 1
    assert products[0].sku == "BRS-BEEF-TEST"
    assert products[0].current_stock == 12


def test_list_orders_combines_movements_in_reverse_chronological_order(
    inventory_session: Session,
) -> None:
    product_id = create_test_product(inventory_session)
    create_inbound(
        IngredientEntryCreate(
            ingredient_id=product_id,
            quantity=10,
            supplier_name="Proveedor de prueba",
            location_id=1,
        ),
        inventory_session,
        {"id": 7},
    )
    create_outbound(
        IngredientExitCreate(
            ingredient_id=product_id,
            quantity=2,
            reason="waste",
            location_id=1,
        ),
        inventory_session,
        {"id": 7},
    )

    orders = list_orders(inventory_session)

    assert [order.type for order in orders] == ["outbound", "inbound"]
    assert all(order.ingredient_name == "Falda de ternera" for order in orders)


def test_unknown_product_returns_not_found(inventory_session: Session) -> None:
    with pytest.raises(HTTPException) as error:
        get_product(999, inventory_session)

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"ingredient_id": 1, "quantity": 1, "reason": "adjustment", "location_id": 1},
        {"ingredient_id": 1, "quantity": 1, "reason": "consumption", "location_id": 15},
        {"ingredient_id": 1, "quantity": 0, "reason": "consumption", "location_id": 1},
    ],
)
def test_outbound_schema_rejects_invalid_business_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        IngredientExitCreate(**payload)


def test_inventory_models_do_not_store_current_stock() -> None:
    assert "current_stock" not in Ingredient.model_fields


@pytest.mark.parametrize("location_id,country,currency", [(1, "CO", "COP"), (8, "US", "USD"), (11, "CO", "COP"), (14, "US", "USD")])
def test_location_currency_comes_from_catalog(location_id: int, country: str, currency: str) -> None:
    location = location_for(location_id)
    assert location["country"] == country
    assert location["currency"] == currency
    assert location["code"] == f"L{location_id:02d}"


@pytest.mark.parametrize("price,expected", [("110.00", None), ("90.00", None), ("111.00", 11.0), ("89.00", -11.0)])
def test_price_variance_requires_strict_threshold(price: str, expected: float | None) -> None:
    result = price_variance(Decimal(price), [Decimal("100.00")] * 3, Decimal(10))
    if expected is None:
        assert result is None
    else:
        assert result["variance_pct"] == expected
        assert result["reference_price"] == "100.00"


def test_price_variance_requires_three_positive_observations() -> None:
    assert price_variance(Decimal(200), [Decimal(100), Decimal(100), Decimal(0)], Decimal(10)) is None


@pytest.fixture
def priced_supplier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.brasaland_api.routes.inventory.get_supplier_by_id", lambda supplier_id: {
        "id": supplier_id, "name": "Proveedor de pruebas", "status": "active",
        "currency": "USD" if supplier_id == 8 else "COP",
    })


def priced_purchase(session: Session, product_id: int, price: str = "100.00", quantity: float = 10, location_id: int = 1):
    return create_inbound(IngredientEntryCreate(
        ingredient_id=product_id, quantity=quantity, supplier_id=8 if location_id == 8 else 7,
        unit_price=Decimal(price), currency="USD" if location_id == 8 else "COP", location_id=location_id,
    ), session, {"id": 42})


def test_confirmed_purchase_and_price_variance_follow_contract(inventory_session: Session, priced_supplier: None) -> None:
    product_id = create_test_product(inventory_session)
    first = priced_purchase(inventory_session, product_id)
    assert [event["event_type"] for event in first.telemetry_events] == ["inbound_order_created"]
    assert "INSUFFICIENT_PRICE_HISTORY" in first.telemetry_issues
    priced_purchase(inventory_session, product_id)
    priced_purchase(inventory_session, product_id)
    changed = priced_purchase(inventory_session, product_id, "120.00")
    assert [event["event_type"] for event in changed.telemetry_events] == ["inbound_order_created", "ingredient_price_variance_detected"]
    for event in changed.telemetry_events:
        event_validator().validate(event)
        assert event["userId"] == "42"
        assert event["properties"]["country"] == "CO"
    variance = changed.telemetry_events[1]["properties"]
    assert variance["reference_price"] == "100.00"
    assert variance["variance_pct"] == 20
    assert variance["quantity"] == 10
    assert changed.telemetry_events[0]["properties"]["total_amount"] == "1200.00"
    assert all(not order.telemetry_events for order in list_orders(inventory_session))


def test_consumption_threshold_emits_only_on_crossing(inventory_session: Session, priced_supplier: None) -> None:
    product_id = create_test_product(inventory_session)
    priced_purchase(inventory_session, product_id)
    equal = create_outbound(IngredientExitCreate(
        ingredient_id=product_id, quantity=3, reason="consumption", location_id=1, minimum_stock=7,
    ), inventory_session, {"id": 42})
    assert [event["event_type"] for event in equal.telemetry_events] == ["outbound_order_created"]
    crossing = create_outbound(IngredientExitCreate(
        ingredient_id=product_id, quantity=1, reason="consumption", location_id=1,
    ), inventory_session, {"id": 42})
    assert [event["event_type"] for event in crossing.telemetry_events] == ["outbound_order_created", "stock_threshold_triggered"]
    threshold = crossing.telemetry_events[1]["properties"]
    assert (threshold["stock_before"], threshold["stock_after"], threshold["minimum_stock"]) == (7, 6, 7)
    for event in crossing.telemetry_events:
        event_validator().validate(event)
    below = create_outbound(IngredientExitCreate(
        ingredient_id=product_id, quantity=1, reason="consumption", location_id=1,
    ), inventory_session, {"id": 42})
    assert [event["event_type"] for event in below.telemetry_events] == ["outbound_order_created"]
    priced_purchase(inventory_session, product_id)
    recrossing = create_outbound(IngredientExitCreate(
        ingredient_id=product_id, quantity=9, reason="consumption", location_id=1,
    ), inventory_session, {"id": 42})
    assert recrossing.telemetry_events[-1]["event_type"] == "stock_threshold_triggered"
    assert get_product(product_id, inventory_session, location_id=1).location_minimum_stock == 7


@pytest.mark.parametrize("reason", ["expired", "kitchen_error", "theft_suspected"])
def test_waste_has_explicit_cause_and_is_not_consumption(inventory_session: Session, priced_supplier: None, reason: str) -> None:
    product_id = create_test_product(inventory_session)
    priced_purchase(inventory_session, product_id)
    result = create_outbound(IngredientExitCreate(
        ingredient_id=product_id, quantity=1, reason="waste", waste_reason=reason, location_id=1, minimum_stock=0,
    ), inventory_session, {"id": 42})
    assert len(result.telemetry_events) == 1
    event = result.telemetry_events[0]
    assert event["event_type"] == "stock_waste_registered"
    assert event["properties"]["reason"] == reason
    event_validator().validate(event)


def test_waste_event_uses_weighted_historical_purchase_cost(
    inventory_session: Session, priced_supplier: None
) -> None:
    product_id = create_test_product(inventory_session)
    priced_purchase(inventory_session, product_id, "100.00", quantity=10)
    priced_purchase(inventory_session, product_id, "120.00", quantity=5)

    result = create_outbound(
        IngredientExitCreate(
            ingredient_id=product_id,
            quantity=2,
            reason="waste",
            waste_reason="expired",
            location_id=1,
        ),
        inventory_session,
        {"id": 42},
    )

    properties = result.telemetry_events[0]["properties"]
    assert properties["unit_price"] == "106.67"
    assert properties["total_amount"] == "213.34"
    event_validator().validate(result.telemetry_events[0])


def test_local_stock_cannot_be_consumed_from_another_location(inventory_session: Session, priced_supplier: None) -> None:
    product_id = create_test_product(inventory_session)
    priced_purchase(inventory_session, product_id)
    assert get_product(product_id, inventory_session, location_id=2).current_stock == 0
    with pytest.raises(HTTPException) as error:
        create_outbound(IngredientExitCreate(
            ingredient_id=product_id, quantity=1, reason="consumption", location_id=2,
        ), inventory_session, {"id": 42})
    assert error.value.status_code == 400
    assert not inventory_session.exec(select(IngredientExit)).all()


def test_country_and_currency_follow_location_not_ingredient(inventory_session: Session, priced_supplier: None) -> None:
    product_id = create_test_product(inventory_session)
    result = priced_purchase(inventory_session, product_id, location_id=8)
    assert result.telemetry_events[0]["properties"]["country"] == "US"
    assert result.telemetry_events[0]["properties"]["currency"] == "USD"
    assert result.telemetry_events[0]["properties"]["location_id"] == "L08"


@pytest.mark.parametrize("method,path", [("PATCH", "/inventory/products/{product_id}"), ("POST", "/inventory/products")])
def test_direct_stock_edit_is_rejected_and_validated_by_ingestion(
    inventory_session: Session, method: str, path: str,
) -> None:
    from services.brasaland_api.auth import get_current_user
    from services.brasaland_api.database import get_db
    from services.brasaland_api.routes.inventory import router
    from services.brasaland_api.routes.telemetry import router as telemetry_router

    product_id = create_test_product(inventory_session)
    app = FastAPI()
    app.include_router(router)
    app.include_router(telemetry_router)
    app.dependency_overrides[get_db] = lambda: inventory_session
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    client = TestClient(app)
    response = client.request(method, path.format(product_id=product_id), json={
        "current_stock": "private@example.com", "location_id": 1,
    })
    assert response.status_code == 403
    assert "private@example.com" not in response.text
    event = response.json()["detail"]["telemetry_events"][0]
    assert event["event_type"] == "direct_stock_edit_rejected"
    assert event["properties"]["quantity"] is None
    assert event["properties"]["attempted_fields"] == ["current_stock"]
    assert client.post("/telemetry/events", json={"events": [event]}).status_code == 200
    assert get_product(product_id, inventory_session).current_stock == 0


def test_failed_commit_cannot_publish_success(inventory_session: Session, priced_supplier: None, monkeypatch: pytest.MonkeyPatch) -> None:
    product_id = create_test_product(inventory_session)
    published = []
    monkeypatch.setattr("services.brasaland_api.routes.inventory.make_event", lambda *args: published.append(args))
    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")
    monkeypatch.setattr(inventory_session, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        priced_purchase(inventory_session, product_id)
    inventory_session.rollback()
    assert published == []
    assert not inventory_session.exec(select(IngredientEntry)).all()


def test_additive_migration_preserves_rows_and_is_idempotent() -> None:
    engine = create_engine("sqlite://")
    metadata = MetaData()
    additions = {"supplier_id", "unit_price", "currency", "waste_reason"}
    for model in (Ingredient, IngredientEntry, IngredientExit):
        Table(model.__tablename__, metadata, *[
            Column(column.name, column.type, primary_key=column.primary_key, nullable=column.nullable)
            for column in model.__table__.columns if column.name not in additions
        ])
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(metadata.tables["ingredients"].insert(), Ingredient(
            id=1, name="Producto", sku="LEGACY", unit="kg", category="meat", country="CO",
        ).model_dump())
        connection.execute(metadata.tables["ingredient_entries"].insert(), {
            "id": 1, "ingredient_id": 1, "quantity": 10, "supplier_name": "Historico",
            "location_id": 1, "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc), "user_uuid": "42",
        })
    assert migrate_inventory_telemetry(engine)
    assert "unit_price" not in {column["name"] for column in inspect(engine).get_columns("ingredient_entries")}
    migrate_inventory_telemetry(engine, apply=True)
    assert migrate_inventory_telemetry(engine) == []
    with Session(engine) as session:
        entry = session.get(IngredientEntry, 1)
        assert entry.supplier_name == "Historico"
        assert entry.unit_price is None
        assert entry.quantity == 10