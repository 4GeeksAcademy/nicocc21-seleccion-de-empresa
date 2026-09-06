from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from services.brasaland_api.models import (
    Country,
    Currency,
    SupplierCategory,
    SupplierCreate,
    SupplierStatus,
    SupplierUpdateRate,
    SupplierUpdateStatus,
)
from services.brasaland_api.routes import suppliers


UPDATED_AT = datetime(2026, 9, 6, tzinfo=timezone.utc)


def supplier_row(supplier_id: int = 1) -> dict[str, object]:
    return {
        "id": supplier_id,
        "name": "Distribuciones Andinas",
        "country": "Colombia",
        "categories": ["verduras_y_hortalizas"],
        "rate_per_unit": 12500,
        "currency": "COP",
        "status": "active",
        "contact_email": "compras@andinas.test",
        "notes": None,
        "updated_at": UPDATED_AT,
    }


def supplier_payload() -> SupplierCreate:
    return SupplierCreate(
        name="Distribuciones Andinas",
        country=Country.colombia,
        categories=[SupplierCategory.verduras_y_hortalizas],
        rate_per_unit=12500,
        currency=Currency.cop,
        status=SupplierStatus.active,
        contact_email="compras@andinas.test",
    )


def test_create_supplier_returns_the_new_supplier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suppliers, "create_supplier", lambda data: supplier_row())

    result = suppliers.create_supplier_endpoint(supplier_payload())

    assert result.id == 1
    assert result.name == "Distribuciones Andinas"
    assert result.status == SupplierStatus.active


def test_list_suppliers_returns_filtered_business_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        suppliers,
        "list_suppliers",
        lambda country, category: [supplier_row(1)] if country == "Colombia" else [],
    )

    result = suppliers.list_suppliers_endpoint(
        country=Country.colombia,
        category=SupplierCategory.verduras_y_hortalizas,
    )

    assert len(result) == 1
    assert result[0].country == Country.colombia


def test_get_supplier_returns_not_found_for_unknown_supplier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(suppliers, "get_supplier_by_id", lambda supplier_id: None)

    with pytest.raises(HTTPException) as error:
        suppliers.get_supplier_endpoint(999)

    assert error.value.detail == "Proveedor no encontrado"


def test_update_supplier_rate_returns_updated_supplier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updated = supplier_row()
    updated["rate_per_unit"] = 14000
    monkeypatch.setattr(suppliers, "update_supplier_rate", lambda supplier_id, rate: updated)

    result = suppliers.update_supplier_rate_endpoint(1, SupplierUpdateRate(rate_per_unit=14000))

    assert result.rate_per_unit == 14000


def test_update_supplier_status_returns_not_found_for_unknown_supplier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(suppliers, "update_supplier_status", lambda supplier_id, status: None)

    with pytest.raises(HTTPException) as error:
        suppliers.update_supplier_status_endpoint(
            999,
            SupplierUpdateStatus(status=SupplierStatus.suspended),
        )

    assert error.value.detail == "Proveedor no encontrado"


def test_delete_supplier_translates_storage_failure_to_business_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_delete(supplier_id: int) -> bool:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(suppliers, "delete_supplier", failing_delete)

    with pytest.raises(HTTPException) as error:
        suppliers.delete_supplier_endpoint(1)

    assert error.value.detail == "Error al eliminar proveedor"
