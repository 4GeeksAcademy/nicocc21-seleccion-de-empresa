"""Router de inventario — Hito 5 (nivel academia).

Todos los endpoints bajo el prefijo `/inventory/`. Los insumos y órdenes
viven en Supabase (SQLModel); el stock siempre se deriva del historial de
órdenes y NUNCA se guarda como columna editable.

Seguridad:
  - Endpoints de escritura (POST) requieren autenticación JWT.
  - El `user_uuid` se extrae automáticamente del token, no del body.
  - Endpoints de lectura (GET) son públicos (según CONTEXT.md).

Dominio (alineado con el contexto de Hito 5):
    - Categorías: "meat", "produce", "sauce", "beverage", "packaging", "cleaning"
    - Razones de salida: "consumption", "waste"
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlmodel import Session, select

from services.brasaland_api.auth import get_current_user
from services.brasaland_api.cache import cache, cached
from services.brasaland_api.database import get_db, get_supplier_by_id
from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit, IngredientLocation
from services.brasaland_api.inventory_telemetry import (
    canonical_unit, event_context, inventory_base, location_for, locations,
    make_event, money, price_variance, workflow_completed,
)
from services.brasaland_api.schemas import (
    IngredientCreate,
    IngredientEntryCreate,
    IngredientEntryOut,
    IngredientExitCreate,
    IngredientExitOut,
    IngredientOut,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])
_logger = logging.getLogger(__name__)
PRICE_VARIANCE_THRESHOLD = Decimal(os.getenv("TELEMETRY_PRICE_VARIANCE_THRESHOLD", "10"))
if not PRICE_VARIANCE_THRESHOLD.is_finite() or PRICE_VARIANCE_THRESHOLD <= 0:
    raise RuntimeError("TELEMETRY_PRICE_VARIANCE_THRESHOLD debe ser positivo")


async def reject_direct_stock_fields(
    request: Request,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    try:
        body = await request.json()
    except ValueError:
        return
    if not isinstance(body, dict):
        return
    attempted = [name for name in ("stock", "stockActual", "current_stock") if name in body]
    if not attempted:
        return
    product_id = str(request.path_params.get("product_id", ""))
    ingredient = session.get(Ingredient, int(product_id)) if product_id.isdecimal() else None
    location_id = body.get("location_id")
    location = location_for(location_id) if type(location_id) is int and 1 <= location_id <= 14 else None
    event = make_event("direct_stock_edit_rejected", {
        "location_id": location["code"] if location else None,
        "country": location["country"] if location else None,
        "currency": location["currency"] if location else None,
        "product_id": str(ingredient.id) if ingredient else None,
        "product_category": ingredient.category if ingredient else None,
        "unit": canonical_unit(ingredient.unit) if ingredient else None,
        "quantity": None, "rejection_code": "DIRECT_STOCK_EDIT_FORBIDDEN",
        "operation": "direct_stock_edit", "attempted_fields": attempted,
    }, event_context(request, str(current_user["id"])))
    raise HTTPException(status_code=403, detail={
        "code": "DIRECT_STOCK_EDIT_FORBIDDEN", "telemetry_events": [event],
    })


# =============================================================================
# Helpers de stock (siempre derivado, nunca almacenado)
# =============================================================================


def _sum_quantity(session: Session, model, ingredient_id: int, location_id: int | None = None) -> float:
    """Suma total de quantity para un ingrediente en un modelo de movimiento."""
    stmt = select(func.coalesce(func.sum(model.quantity), 0.0)).where(
        model.ingredient_id == ingredient_id
    )
    if location_id is not None:
        stmt = stmt.where(model.location_id == location_id)
    return float(session.exec(stmt).one())


def _calculate_stock(session: Session, ingredient_id: int, location_id: int | None = None) -> float:
    """Stock = SUM(entries) - SUM(exits). Nunca se almacena."""
    entries_total = _sum_quantity(session, IngredientEntry, ingredient_id, location_id)
    exits_total = _sum_quantity(session, IngredientExit, ingredient_id, location_id)
    return round(entries_total - exits_total, 10 if location_id is not None else 2)


def _stock_map_for_all(session: Session) -> dict[int, float]:
    """Calcula el stock de TODOS los ingredientes en 2 queries agregadas.
    Evita el problema N+1 de consultar por cada ingrediente en un loop."""
    entries_stmt = select(
        IngredientEntry.ingredient_id, func.sum(IngredientEntry.quantity)
    ).group_by(IngredientEntry.ingredient_id)
    exits_stmt = select(
        IngredientExit.ingredient_id, func.sum(IngredientExit.quantity)
    ).group_by(IngredientExit.ingredient_id)

    entries_sums = dict(session.exec(entries_stmt).all())
    exits_sums = dict(session.exec(exits_stmt).all())

    all_ids = set(entries_sums) | set(exits_sums)
    return {
        ingredient_id: round(
            entries_sums.get(ingredient_id, 0.0) - exits_sums.get(ingredient_id, 0.0),
            2,
        )
        for ingredient_id in all_ids
    }


def _get_ingredient_or_404(session: Session, ingredient_id: int) -> Ingredient:
    """Obtiene un ingrediente por ID o lanza 404."""
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insumo con ID {ingredient_id} no encontrado",
        )
    return ingredient


def _lock_ingredient(session: Session, ingredient_id: int) -> Ingredient:
    ingredient = session.exec(
        select(Ingredient).where(Ingredient.id == ingredient_id).with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if ingredient is None:
        raise HTTPException(status_code=404, detail=f"Insumo con ID {ingredient_id} no encontrado")
    return ingredient


# =============================================================================
# Products — GET listado con filtros
# =============================================================================


@router.get("/locations", response_model=list[dict[str, object]])
def list_inventory_locations() -> list[dict[str, object]]:
    return locations()


@router.get(
    "/products",
    response_model=list[IngredientOut],
    summary="Listar insumos",
    description=(
        "Devuelve todos los insumos del inventario con su stock actual calculado "
        "dinámicamente (SUM entradas - SUM salidas). Soporta filtros opcionales "
        "por categoría y país. [Cacheado TTL=60s]"
    ),
)
@cached(ttl_seconds=60, skip_args={"session"}, prefix="inventory")
def list_products(
    session: Session = Depends(get_db),
    categoria: Literal["meat", "produce", "sauce", "beverage", "packaging", "cleaning"] | None = Query(
        default=None, description="Filtrar por categoría de insumo"
    ),
    pais: Literal["CO", "US"] | None = Query(
        default=None, description="Filtrar por país (CO=Colombia, US=Florida)"
    ),
) -> list[IngredientOut]:
    stmt = select(Ingredient)
    if categoria:
        stmt = stmt.where(Ingredient.category == categoria)
    if pais:
        stmt = stmt.where(Ingredient.country == pais)

    ingredients = session.exec(stmt).all()
    stock_map = _stock_map_for_all(session)

    return [
        IngredientOut(
            **ingredient.model_dump(), current_stock=stock_map.get(ingredient.id, 0.0)
        )
        for ingredient in ingredients
    ]


# =============================================================================
# Products — POST crear insumo (requiere auth)
# =============================================================================


@router.post(
    "/products",
    dependencies=[Depends(reject_direct_stock_fields)],
    response_model=IngredientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear insumo",
    description=(
        "Crea un nuevo insumo en el inventario. Requiere autenticación. "
        "El stock inicial es siempre 0.0 — solo se acumula mediante órdenes de entrada."
    ),
    responses={
        201: {"description": "Insumo creado exitosamente"},
        400: {"description": "Ya existe un insumo con ese SKU"},
        401: {"description": "Autenticación requerida"},
    },
)
def create_product(
    payload: IngredientCreate,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> IngredientOut:
    existing = session.exec(
        select(Ingredient).where(Ingredient.sku == payload.sku)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un insumo con el SKU '{payload.sku}'",
        )

    ingredient = Ingredient(**payload.model_dump())
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)

    # Los datos subyacentes cambiaron → invalidar caché del dominio inventory
    cache.invalidate("inventory")
    _logger.info("Caché de inventario invalidada tras crear insumo %s", ingredient.id)

    return IngredientOut(**ingredient.model_dump(), current_stock=0.0)


# =============================================================================
# Products — GET por ID
# =============================================================================


@router.get(
    "/products/{product_id}",
    response_model=IngredientOut,
    summary="Obtener insumo por ID",
    description="Devuelve un insumo específico con su stock actual calculado dinámicamente. [Cacheado TTL=60s]",
    responses={
        200: {"description": "Insumo encontrado"},
        404: {"description": "Insumo no encontrado"},
    },
)
@cached(ttl_seconds=60, skip_args={"session"}, prefix="inventory")
def get_product(
    product_id: int, session: Session = Depends(get_db),
    location_id: Annotated[int | None, Query(ge=1, le=14)] = None,
) -> IngredientOut:
    ingredient = _get_ingredient_or_404(session, product_id)
    current_stock = _calculate_stock(session, product_id, location_id)
    minimum = session.get(IngredientLocation, (product_id, location_id)) if location_id else None
    return IngredientOut(
        **ingredient.model_dump(), current_stock=current_stock, location_id=location_id,
        location_minimum_stock=minimum.minimum_stock if minimum else None,
    )


@router.patch("/products/{product_id}", dependencies=[Depends(reject_direct_stock_fields)])
def reject_product_update(product_id: int, current_user: dict = Depends(get_current_user)) -> None:
    raise HTTPException(status_code=400, detail="PRODUCT_UPDATE_NOT_SUPPORTED")


# =============================================================================
# Orders — inbound (entrada / recepción de proveedor) — requiere auth
# =============================================================================


@router.post(
    "/orders/inbound",
    response_model=IngredientEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar entrada de stock",
    description=(
        "Registra una recepción de mercancía de proveedor. "
        "Incrementa el stock del insumo. "
        "El user_uuid se extrae automáticamente del token JWT."
    ),
    responses={
        201: {"description": "Entrada registrada exitosamente"},
        401: {"description": "Autenticación requerida"},
        404: {"description": "Insumo no encontrado"},
    },
)
def create_inbound(
    payload: IngredientEntryCreate,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    request: Request = None,
) -> IngredientEntryOut:
    ingredient = _lock_ingredient(session, payload.ingredient_id)
    location = location_for(payload.location_id)
    data = payload.model_dump()
    previous_prices: list[Decimal] = []
    now = datetime.now(timezone.utc)
    if payload.supplier_id is not None:
        supplier = get_supplier_by_id(payload.supplier_id)
        if supplier is None or supplier.get("status") != "active":
            raise HTTPException(status_code=400, detail="SUPPLIER_UNAVAILABLE")
        if payload.currency != location["currency"] or supplier.get("currency") != payload.currency:
            raise HTTPException(status_code=422, detail="LOCATION_CURRENCY_MISMATCH")
        if len(money(Decimal(str(payload.quantity)) * payload.unit_price)) > 24:
            raise HTTPException(status_code=422, detail="ORDER_AMOUNT_TOO_LARGE")
        data["supplier_name"] = str(supplier["name"])
        country_locations = [item["id"] for item in locations() if item["country"] == location["country"]]
        previous_prices = list(session.exec(select(IngredientEntry.unit_price).where(
            IngredientEntry.ingredient_id == payload.ingredient_id,
            IngredientEntry.supplier_id == payload.supplier_id,
            IngredientEntry.currency == payload.currency,
            IngredientEntry.location_id.in_(country_locations),
            IngredientEntry.unit_price > 0,
            IngredientEntry.created_at >= now - timedelta(days=30),
            IngredientEntry.created_at < now,
        ).order_by(IngredientEntry.created_at, IngredientEntry.id)).all())

    entry = IngredientEntry(
        **data, created_at=now,
        user_uuid=str(current_user["id"]),  # del JWT, no del body
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # El stock derivado y el historial de órdenes cambiaron → invalidar caché
    cache.invalidate("inventory")
    _logger.info("Caché de inventario invalidada tras entrada de stock (insumo %s)", payload.ingredient_id)

    context = event_context(request, str(current_user["id"]))
    events = []
    issues = []
    if entry.supplier_id is None or entry.unit_price is None or entry.currency is None:
        issues.append("LEGACY_PURCHASE_WITHOUT_COST")
    elif canonical_unit(ingredient.unit) is None:
        issues.append("UNSUPPORTED_UNIT")
    else:
        base = inventory_base(ingredient, location, entry.quantity)
        purchase = {**base, "order_id": str(entry.id), "supplier_id": str(entry.supplier_id),
                    "unit_price": money(entry.unit_price), "total_amount": money(Decimal(str(entry.quantity)) * entry.unit_price)}
        events.append(make_event("inbound_order_created", purchase, context, entry.created_at))
        variance = price_variance(entry.unit_price, previous_prices, PRICE_VARIANCE_THRESHOLD)
        if variance:
            events.append(make_event("ingredient_price_variance_detected", {
                **base, "order_id": str(entry.id), "supplier_id": str(entry.supplier_id), **variance,
            }, context, entry.created_at))
        elif len(previous_prices) < 3:
            issues.append("INSUFFICIENT_PRICE_HISTORY")
    events.extend(workflow_completed(context, "inventory_inbound", entry.id, entry.created_at))
    return IngredientEntryOut(**entry.model_dump(), ingredient_name=ingredient.name, telemetry_events=events, telemetry_issues=issues)


# =============================================================================
# Orders — outbound (salida / consumo o merma) — requiere auth
# =============================================================================


@router.post(
    "/orders/outbound",
    response_model=IngredientExitOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar salida de stock",
    description=(
        "Registra un consumo o merma de insumo. "
        "Reduce el stock del insumo. Valida que haya stock suficiente antes "
        "de persistir. El user_uuid se extrae automáticamente del token JWT."
    ),
    responses={
        201: {"description": "Salida registrada exitosamente"},
        400: {"description": "Stock insuficiente para la cantidad solicitada"},
        401: {"description": "Autenticación requerida"},
        404: {"description": "Insumo no encontrado"},
    },
)
def create_outbound(
    payload: IngredientExitCreate,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    request: Request = None,
) -> IngredientExitOut:
    ingredient = _lock_ingredient(session, payload.ingredient_id)

    available = _calculate_stock(session, payload.ingredient_id, payload.location_id)
    if payload.quantity > available:
        ctx = event_context(request, str(current_user["id"]))
        location = location_for(payload.location_id)
        event = make_event("inventory_order_rejected", {
            "order_type": "outbound", "rejection_code": "INSUFFICIENT_STOCK",
            "location_id": location["code"], "product_id": str(ingredient.id),
        }, ctx)
        raise HTTPException(
            status_code=400,
            detail={"code": "INSUFFICIENT_STOCK", "telemetry_events": [event]},
        )

    minimum = session.get(IngredientLocation, (payload.ingredient_id, payload.location_id))
    if payload.minimum_stock is not None:
        if minimum is None:
            minimum = IngredientLocation(ingredient_id=payload.ingredient_id, location_id=payload.location_id, minimum_stock=payload.minimum_stock)
        else:
            minimum.minimum_stock = payload.minimum_stock
        session.add(minimum)
    exit_ = IngredientExit(
        **payload.model_dump(exclude={"minimum_stock"}),
        user_uuid=str(current_user["id"]),
    )
    session.add(exit_)
    session.commit()
    session.refresh(exit_)

    # El stock derivado y el historial de órdenes cambiaron → invalidar caché
    cache.invalidate("inventory")
    _logger.info("Caché de inventario invalidada tras salida de stock (insumo %s)", payload.ingredient_id)

    context = event_context(request, str(current_user["id"]))
    base = inventory_base(ingredient, location_for(exit_.location_id), exit_.quantity)
    events = []
    issues = []
    if canonical_unit(ingredient.unit) is None:
        issues.append("UNSUPPORTED_UNIT")
    else:
        if exit_.reason == "consumption":
            events.append(make_event("outbound_order_created", {**base, "order_id": str(exit_.id), "reason": "consumption"}, context, exit_.created_at))
        elif exit_.waste_reason:
            events.append(make_event("stock_waste_registered", {**base, "order_id": str(exit_.id), "reason": exit_.waste_reason}, context, exit_.created_at))
        else:
            issues.append("LEGACY_WASTE_WITHOUT_CAUSE")
        after = round(available - exit_.quantity, 10)
        if minimum and available >= minimum.minimum_stock and after < minimum.minimum_stock:
            events.append(make_event("stock_threshold_triggered", {
                **base, "order_id": str(exit_.id), "stock_before": available,
                "stock_after": after, "minimum_stock": minimum.minimum_stock,
            }, context, exit_.created_at))
        if minimum is None:
            issues.append("LOCAL_MINIMUM_NOT_CONFIGURED")
    events.extend(workflow_completed(context, "inventory_outbound", exit_.id, exit_.created_at))
    return IngredientExitOut(**exit_.model_dump(), ingredient_name=ingredient.name, telemetry_events=events, telemetry_issues=issues)


# =============================================================================
# Orders — listado combinado (entradas + salidas)
# =============================================================================


@router.get(
    "/orders",
    response_model=list[IngredientEntryOut | IngredientExitOut],
    summary="Listar órdenes de inventario",
    description=(
        "Devuelve el historial completo de movimientos de inventario "
        "(entradas y salidas) en orden cronológico inverso. "
        "Cada movimiento incluye el nombre del insumo (via join) para evitar N+1. "
        "[Cacheado TTL=60s]"
    ),
)
@cached(ttl_seconds=60, skip_args={"session"}, prefix="inventory")
def list_orders(
    session: Session = Depends(get_db),
) -> list[IngredientEntryOut | IngredientExitOut]:
    entry_rows = session.exec(
        select(IngredientEntry, Ingredient.name).join(
            Ingredient, IngredientEntry.ingredient_id == Ingredient.id
        )
    ).all()
    exit_rows = session.exec(
        select(IngredientExit, Ingredient.name).join(
            Ingredient, IngredientExit.ingredient_id == Ingredient.id
        )
    ).all()

    orders: list[IngredientEntryOut | IngredientExitOut] = [
        IngredientEntryOut(**entry.model_dump(), ingredient_name=name)
        for entry, name in entry_rows
    ]
    orders += [
        IngredientExitOut(**exit_.model_dump(), ingredient_name=name)
        for exit_, name in exit_rows
    ]

    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders
