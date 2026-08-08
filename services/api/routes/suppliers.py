from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from services.api.database import (
    create_supplier,
    delete_supplier,
    get_supplier_by_id,
    list_suppliers,
    update_supplier_rate,
    update_supplier_status,
)
from services.api.models import (
    Country,
    SupplierCategory,
    SupplierCreate,
    SupplierOut,
    SupplierUpdateRate,
    SupplierUpdateStatus,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier_endpoint(payload: SupplierCreate) -> SupplierOut:
    created = create_supplier(payload.model_dump(mode="json"))
    return SupplierOut.model_validate(created)


@router.get("", response_model=list[SupplierOut])
def list_suppliers_endpoint(
    country: Country | None = Query(default=None),
    category: SupplierCategory | None = Query(default=None),
) -> list[SupplierOut]:
    rows = list_suppliers(
        country=country.value if country else None,
        category=category.value if category else None,
    )
    return [SupplierOut.model_validate(row) for row in rows]


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier_endpoint(supplier_id: int) -> SupplierOut:
    supplier = get_supplier_by_id(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return SupplierOut.model_validate(supplier)


@router.patch("/{supplier_id}/rate", response_model=SupplierOut)
def update_supplier_rate_endpoint(
    supplier_id: int, payload: SupplierUpdateRate
) -> SupplierOut:
    supplier = update_supplier_rate(supplier_id, payload.rate_per_unit)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return SupplierOut.model_validate(supplier)


@router.patch("/{supplier_id}/status", response_model=SupplierOut)
def update_supplier_status_endpoint(
    supplier_id: int, payload: SupplierUpdateStatus
) -> SupplierOut:
    supplier = update_supplier_status(supplier_id, payload.status.value)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return SupplierOut.model_validate(supplier)


@router.delete("/{supplier_id}")
def delete_supplier_endpoint(supplier_id: int) -> dict[str, str]:
    deleted = delete_supplier(supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Proveedor eliminado"}
