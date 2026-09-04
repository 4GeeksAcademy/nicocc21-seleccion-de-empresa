from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.api.auth import get_current_user
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

router = APIRouter(
    prefix="/suppliers",
    tags=["suppliers"],
    dependencies=[Depends(get_current_user)],
)
_logger = logging.getLogger(__name__)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier_endpoint(payload: SupplierCreate) -> SupplierOut:
    try:
        created = create_supplier(payload.model_dump(mode="json"))
        return SupplierOut.model_validate(created)
    except Exception:
        _logger.exception("Error al crear proveedor")
        raise HTTPException(status_code=500, detail="Error al crear proveedor")


@router.get("", response_model=list[SupplierOut])
def list_suppliers_endpoint(
    country: Country | None = Query(default=None),
    category: SupplierCategory | None = Query(default=None),
) -> list[SupplierOut]:
    try:
        rows = list_suppliers(
            country=country.value if country else None,
            category=category.value if category else None,
        )
        return [SupplierOut.model_validate(row) for row in rows]
    except Exception:
        _logger.exception("Error al listar proveedores")
        raise HTTPException(status_code=500, detail="Error al listar proveedores")


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier_endpoint(supplier_id: int) -> SupplierOut:
    try:
        supplier = get_supplier_by_id(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return SupplierOut.model_validate(supplier)
    except HTTPException:
        raise
    except Exception:
        _logger.exception("Error al obtener proveedor %s", supplier_id)
        raise HTTPException(status_code=500, detail="Error al obtener proveedor")


@router.patch("/{supplier_id}/rate", response_model=SupplierOut)
def update_supplier_rate_endpoint(
    supplier_id: int, payload: SupplierUpdateRate
) -> SupplierOut:
    try:
        supplier = update_supplier_rate(supplier_id, payload.rate_per_unit)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return SupplierOut.model_validate(supplier)
    except HTTPException:
        raise
    except Exception:
        _logger.exception("Error al actualizar tarifa de proveedor %s", supplier_id)
        raise HTTPException(status_code=500, detail="Error al actualizar tarifa")


@router.patch("/{supplier_id}/status", response_model=SupplierOut)
def update_supplier_status_endpoint(
    supplier_id: int, payload: SupplierUpdateStatus
) -> SupplierOut:
    try:
        supplier = update_supplier_status(supplier_id, payload.status.value)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        return SupplierOut.model_validate(supplier)
    except HTTPException:
        raise
    except Exception:
        _logger.exception("Error al actualizar estado de proveedor %s", supplier_id)
        raise HTTPException(status_code=500, detail="Error al actualizar estado")


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier_endpoint(supplier_id: int) -> None:
    try:
        deleted = delete_supplier(supplier_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    except HTTPException:
        raise
    except Exception:
        _logger.exception("Error al eliminar proveedor %s", supplier_id)
        raise HTTPException(status_code=500, detail="Error al eliminar proveedor")
    return {"message": "Proveedor eliminado"}
