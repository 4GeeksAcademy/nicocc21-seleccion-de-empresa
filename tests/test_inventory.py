from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from services.brasaland_api.inventory_models import Ingredient
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
    category: str = "comida",
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
    assert product.category == "comida"
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
            reason="consumo",
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
                reason="merma",
                location_id=1,
            ),
            inventory_session,
            {"id": 43},
        )

    assert error.value.status_code == 400
    assert error.value.detail == (
        "Insufficient stock for ingredient 'Falda de ternera'. "
        "Available: 15.0, requested: 16.0."
    )


def test_list_products_calculates_stock_and_applies_filters(
    inventory_session: Session,
) -> None:
    food_id = create_test_product(inventory_session)
    create_product(
        product_payload(sku="BRS-BEV-TEST", category="bebida", country="US"),
        inventory_session,
        {"id": 7},
    )
    create_inbound(
        IngredientEntryCreate(
            ingredient_id=food_id,
            quantity=12,
            supplier_name="Proveedor de prueba",
            location_id=1,
        ),
        inventory_session,
        {"id": 7},
    )

    products = list_products(inventory_session, categoria="comida", pais="CO")

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
            reason="merma",
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
        {"ingredient_id": 1, "quantity": 1, "reason": "ajuste", "location_id": 1},
        {"ingredient_id": 1, "quantity": 1, "reason": "consumo", "location_id": 15},
        {"ingredient_id": 1, "quantity": 0, "reason": "consumo", "location_id": 1},
    ],
)
def test_outbound_schema_rejects_invalid_business_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        IngredientExitCreate(**payload)


def test_inventory_models_do_not_store_current_stock() -> None:
    assert "current_stock" not in Ingredient.model_fields