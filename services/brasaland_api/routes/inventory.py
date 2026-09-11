"""Router de inventario — Hito 5 (nivel academia).

Todos los endpoints bajo el prefijo `/inventory/`. Los insumos y órdenes
viven en Supabase (SQLModel); el stock siempre se deriva del historial de
órdenes y NUNCA se guarda como columna editable.

Seguridad:
  - Endpoints de escritura (POST) requieren autenticación JWT.
  - El `user_uuid` se extrae automáticamente del token, no del body.
  - Endpoints de lectura (GET) son públicos (según CONTEXT.md).

Dominio (alineado con CONTEXT.md y src/hito2/types.ts):
  - Categorías: "comida", "bebida", "empaque"
  - Razones de salida: "consumo", "merma"
  - Rotación: 7 días (perecederos) | 15 días (bebidas/licores)
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from services.brasaland_api.auth import get_current_user
from services.brasaland_api.database import get_db
from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit
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


# =============================================================================
# Helpers de stock (siempre derivado, nunca almacenado)
# =============================================================================


def _sum_quantity(session: Session, model, ingredient_id: int) -> float:
    """Suma total de quantity para un ingrediente en un modelo de movimiento."""
    stmt = select(func.coalesce(func.sum(model.quantity), 0.0)).where(
        model.ingredient_id == ingredient_id
    )
    return float(session.exec(stmt).one())


def _calculate_stock(session: Session, ingredient_id: int) -> float:
    """Stock = SUM(entries) - SUM(exits). Nunca se almacena."""
    entries_total = _sum_quantity(session, IngredientEntry, ingredient_id)
    exits_total = _sum_quantity(session, IngredientExit, ingredient_id)
    return round(entries_total - exits_total, 2)


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


# =============================================================================
# Products — GET listado con filtros
# =============================================================================


@router.get(
    "/products",
    response_model=list[IngredientOut],
    summary="Listar insumos",
    description=(
        "Devuelve todos los insumos del inventario con su stock actual calculado "
        "dinámicamente (SUM entradas - SUM salidas). Soporta filtros opcionales "
        "por categoría y país."
    ),
)
def list_products(
    session: Session = Depends(get_db),
    categoria: Literal["comida", "bebida", "empaque"] | None = Query(
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

    return IngredientOut(**ingredient.model_dump(), current_stock=0.0)


# =============================================================================
# Products — GET por ID
# =============================================================================


@router.get(
    "/products/{product_id}",
    response_model=IngredientOut,
    summary="Obtener insumo por ID",
    description="Devuelve un insumo específico con su stock actual calculado dinámicamente.",
    responses={
        200: {"description": "Insumo encontrado"},
        404: {"description": "Insumo no encontrado"},
    },
)
def get_product(
    product_id: int, session: Session = Depends(get_db)
) -> IngredientOut:
    ingredient = _get_ingredient_or_404(session, product_id)
    current_stock = _calculate_stock(session, product_id)
    return IngredientOut(**ingredient.model_dump(), current_stock=current_stock)


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
) -> IngredientEntryOut:
    ingredient = _get_ingredient_or_404(session, payload.ingredient_id)

    entry = IngredientEntry(
        **payload.model_dump(),
        user_uuid=str(current_user["id"]),  # del JWT, no del body
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    return IngredientEntryOut(**entry.model_dump(), ingredient_name=ingredient.name)


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
) -> IngredientExitOut:
    ingredient = _get_ingredient_or_404(session, payload.ingredient_id)

    available = _calculate_stock(session, payload.ingredient_id)
    if payload.quantity > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stock insuficiente para '{ingredient.name}'. "
                f"Disponible: {available}, solicitado: {payload.quantity}."
            ),
        )

    exit_ = IngredientExit(
        **payload.model_dump(),
        user_uuid=str(current_user["id"]),
    )
    session.add(exit_)
    session.commit()
    session.refresh(exit_)

    return IngredientExitOut(**exit_.model_dump(), ingredient_name=ingredient.name)


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
        "Cada movimiento incluye el nombre del insumo (via join) para evitar N+1."
    ),
)
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
