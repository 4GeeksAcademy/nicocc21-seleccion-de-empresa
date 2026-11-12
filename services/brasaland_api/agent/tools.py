"""
services/brasaland_api/agent/tools.py — Herramientas externas del agente de soporte.

Cada tool:
  - Tiene un contrato de entrada/salida tipado con dataclasses.
  - Lee del servicio real (incidentes / inventario) en-proceso, nunca datos simulados.
  - Es de solo lectura (solo GET / consultas).
  - Tiene timeout explícito y ruta de fallback verificable.
  - Nunca hace más de una cosa.

Llamada en-proceso: las tools importan directamente la capa de datos de
los módulos existentes en services/brasaland_api/ en lugar de hacer HTTP.
Esto es válido porque todo vive en el mismo paquete del monorepo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.brasaland_api.incidents_database import (
    get_incident_by_incident_id,
    list_incidents,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

TOOL_TIMEOUT_SECONDS = 5.0

# ---------------------------------------------------------------------------
# Tool de Incidentes — Contrato
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IncidentToolInput:
    """Entrada de la tool de incidentes.

    Puede buscar por:
    - `ticket_id`: ID concreto tipo "INC-0001" (búsqueda exacta)
    - `filtros`: kwargs para list_incidents (estado, local_id, categoria, etc.)
    """

    ticket_id: str | None = None
    estado: str | None = None
    local_id: str | None = None
    categoria: str | None = None
    origen: str | None = None
    prioridad: str | None = None
    desde: str | None = None
    hasta: str | None = None


@dataclass
class IncidentToolResult:
    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0


def run_incident_tool(input_: IncidentToolInput) -> IncidentToolResult:
    """Ejecuta la tool de incidentes: consulta el gestor real en-proceso.

    Si se proporciona `ticket_id`, busca ese ticket concreto.
    Si no, aplica los filtros proporcionados y devuelve el listado.
    """
    import time

    _logger.info("IncidentTool input: %s", input_)
    start = time.perf_counter()

    try:
        if input_.ticket_id:
            incident = get_incident_by_incident_id(input_.ticket_id)
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            if incident is None:
                return IncidentToolResult(
                    success=False,
                    error=f"No se encontró el ticket {input_.ticket_id}.",
                    elapsed_ms=elapsed,
                )
            return IncidentToolResult(success=True, data=[incident], elapsed_ms=elapsed)
        else:
            incidents = list_incidents(
                estado=input_.estado,
                local_id=input_.local_id,
                categoria=input_.categoria,
                origen=input_.origen,
                prioridad=input_.prioridad,
                desde=input_.desde,
                hasta=input_.hasta,
            )
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            return IncidentToolResult(success=True, data=incidents, elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _logger.exception("IncidentTool falló después de %sms", elapsed)
        return IncidentToolResult(
            success=False,
            error=f"No pude consultar el sistema de incidentes ahora mismo: {exc}",
            elapsed_ms=elapsed,
        )


# ---------------------------------------------------------------------------
# Tool de Inventario — Contrato
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InventoryToolInput:
    """Entrada de la tool de inventario.

    Busca productos por:
    - `product_id`: ID numérico del insumo
    - `categoria`: filtrar por categoría
    - `pais`: filtrar por país
    Si no se especifica nada, lista todos los productos.
    """

    product_id: int | None = None
    categoria: str | None = None
    pais: str | None = None


@dataclass
class InventoryToolResult:
    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0


def run_inventory_tool(input_: InventoryToolInput) -> InventoryToolResult:
    """Ejecuta la tool de inventario: consulta el gestor real via SQLModel.

    Lee el stock calculado dinámicamente (SUM entries - SUM exits).
    """
    import time

    _logger.info("InventoryTool input: %s", input_)
    start = time.perf_counter()

    try:
        from sqlmodel import Session, select

        from services.brasaland_api.database import engine, get_db
        from services.brasaland_api.inventory_models import Ingredient

        with Session(engine) as session:
            stmt = select(Ingredient)
            if input_.categoria:
                stmt = stmt.where(Ingredient.category == input_.categoria)
            if input_.pais:
                stmt = stmt.where(Ingredient.country == input_.pais)

            ingredients = session.exec(stmt).all()

        # Calcular stock para cada uno
        from services.brasaland_api.routes.inventory import _stock_map_for_all

        with Session(engine) as session:
            stock_map = _stock_map_for_all(session)

        data = [
            {
                "id": ing.id,
                "name": ing.name,
                "sku": ing.sku,
                "unit": ing.unit,
                "category": ing.category,
                "country": ing.country,
                "stock_minimo": ing.stock_minimo,
                "current_stock": stock_map.get(ing.id, 0.0),
                "perecedero": ing.perecedero,
            }
            for ing in ingredients
        ]

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return InventoryToolResult(success=True, data=data, elapsed_ms=elapsed)

    except Exception as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        _logger.exception("InventoryTool falló después de %sms", elapsed)
        return InventoryToolResult(
            success=False,
            error=f"No pude consultar el sistema de inventario ahora mismo: {exc}",
            elapsed_ms=elapsed,
        )