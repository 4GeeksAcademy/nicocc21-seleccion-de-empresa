"""Tools de inventario expuestas vía MCP — SOLO LECTURA.

Por diseño, este módulo rechaza explícitamente cualquier intento de
escritura sobre el inventario. No basta con "no implementar" endpoints
de escritura: el servidor debe responder con un error claro si alguien
intenta modificar datos de inventario a través de este canal.

El stock se lee desde Supabase/PostgreSQL vía SQLModel.
"""

from __future__ import annotations

import logging
from typing import Any

# Scope que necesita esta tool
SCOPE_INVENTORY_READ = "inventory:read"

# Mensaje de rechazo para operaciones de escritura
_WRITE_REJECTION = (
    "Operación no permitida: el inventario es de solo lectura a través de MCP. "
    "Las modificaciones deben realizarse directamente a través de la API REST "
    "de Brasaland con autenticación JWT."
)

_logger = logging.getLogger(__name__)


def _get_engine_and_models():
    """Importación lazy para evitar errores si DATABASE_URL no está configurada.

    La importación se hace al llamar a la tool, no al cargar el módulo.
    Esto permite que el servidor MCP arranque aunque la BD no esté disponible,
    y la tool de inventario devolverá un error claro en lugar de crashear.
    """
    try:
        from sqlmodel import Session as _Session, select as _select
        from services.brasaland_api.database import engine as _engine
        from services.brasaland_api.inventory_models import (
            Ingredient as _Ingredient,
            IngredientEntry as _IngredientEntry,
            IngredientExit as _IngredientExit,
        )
        return _engine, _Session, _select, _Ingredient, _IngredientEntry, _IngredientExit
    except Exception as exc:
        _logger.error("No se pudo conectar a la base de datos de inventario: %s", exc)
        raise RuntimeError(
            "Inventario no disponible: la base de datos no está configurada. "
            "Verifica que DATABASE_URL esté definida."
        ) from exc


def query_inventory(
    category: str | None = None,
    country: str | None = None,
    perecedero: bool | None = None,
    low_stock: bool | None = None,
    location_id: int | None = None,
) -> list[dict[str, Any]]:
    """Consulta ingredientes del inventario con filtros opcionales.

    Args:
        category: Filtrar por categoría (meat, produce, sauce, beverage, packaging, cleaning)
        country: Filtrar por país (CO, US)
        perecedero: Filtrar solo perecederos (true) o no perecederos (false)
        low_stock: Filtrar solo ingredientes con stock por debajo del mínimo
        location_id: Filtrar por ubicación (1-14)

    Returns:
        Lista de ingredientes con stock actual calculado dinámicamente.
        Cada ingrediente incluye: id, name, sku, unit, category, country,
        stock_minimo, perecedero, dias_vida_util, frecuencia_rotacion_dias,
        current_stock.

    Errors:
        -32603: Si la base de datos de inventario no está configurada
                (DATABASE_URL no definida o conexión fallida).
    """
    engine, Session, select, Ingredient, IngredientEntry, IngredientExit = _get_engine_and_models()
    with Session(engine) as session:
        query = select(Ingredient)

        if category:
            query = query.where(Ingredient.category == category)
        if country:
            query = query.where(Ingredient.country == country)
        if perecedero is not None:
            query = query.where(Ingredient.perecedero == perecedero)

        ingredients = session.exec(query).all()

        result: list[dict[str, Any]] = []
        for ing in ingredients:
            # Calcular stock actual dinámicamente
            total_entries = session.exec(
                select(IngredientEntry.quantity).where(
                    IngredientEntry.ingredient_id == ing.id
                )
            ).all()
            total_exits = session.exec(
                select(IngredientExit.quantity).where(
                    IngredientExit.ingredient_id == ing.id
                )
            ).all()

            current_stock = sum(total_entries) - sum(total_exits)

            # Si se pide filtrar por location_id, calcular stock solo de esa locación
            if location_id is not None:
                entries_loc = session.exec(
                    select(IngredientEntry.quantity).where(
                        IngredientEntry.ingredient_id == ing.id,
                        IngredientEntry.location_id == location_id,
                    )
                ).all()
                exits_loc = session.exec(
                    select(IngredientExit.quantity).where(
                        IngredientExit.ingredient_id == ing.id,
                        IngredientExit.location_id == location_id,
                    )
                ).all()
                current_stock = sum(entries_loc) - sum(exits_loc)

            ing_data = {
                "id": ing.id,
                "name": ing.name,
                "sku": ing.sku,
                "unit": ing.unit,
                "category": ing.category,
                "country": ing.country,
                "stock_minimo": ing.stock_minimo,
                "perecedero": ing.perecedero,
                "dias_vida_util": ing.dias_vida_util,
                "frecuencia_rotacion_dias": ing.frecuencia_rotacion_dias,
                "current_stock": current_stock,
            }

            if location_id is not None:
                ing_data["location_id"] = location_id

            result.append(ing_data)

    # Filtrar por low_stock si se solicita (después de calcular)
    if low_stock:
        result = [r for r in result if r["current_stock"] < r["stock_minimo"]]

    _logger.info(
        "query_inventory -> %d resultados (filtros: %s)",
        len(result),
        _filtros_str(category=category, country=country, perecedero=perecedero,
                      low_stock=low_stock, location_id=location_id),
    )
    return result


def reject_inventory_write() -> dict[str, Any]:
    """Rechaza explícitamente cualquier intento de escribir en el inventario.

    Returns:
        Diccionario con mensaje de error indicando que el inventario es solo lectura.

    Raises:
        PermissionError: Siempre (código MCP -32003), indicando que la operación
                         no está permitida. El servidor NO acepta modificaciones
                         de inventario a través de MCP.

    Errors:
        -32003: Permission denied — el inventario es solo lectura vía MCP.
    """
    _logger.warning("reject_inventory_write invocada — rechazando escritura")
    raise PermissionError(_WRITE_REJECTION)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _filtros_str(**kwargs: Any) -> str:
    """Convierte filtros a string legible para logs, omitiendo None."""
    partes = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    return ", ".join(partes) if partes else "sin filtros"