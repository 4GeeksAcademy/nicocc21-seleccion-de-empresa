"""Tools del Incidents Manager expuestas vía MCP.

Todas las operaciones CRUD sobre tickets del sistema de incidencias.

Cada tool registra en log su invocación para trazabilidad.
Los errores de validación se lanzan como ValueError con mensajes
descriptivos (FastMCP los convierte a JSON-RPC error -32602).

Códigos de error MCP utilizados:
  -32602: Invalid params (error de validación como transición de estado inválida)
  -32603: Internal error (fallo inesperado en la base de datos)
"""

from __future__ import annotations

import logging
from typing import Any

# Importaciones del core de incidencias (TinyDB)
from services.brasaland_api.incidents_database import (
    create_incident as _create_incident,
    get_incident as _get_incident,
    get_incidents_summary as _get_incidents_summary,
    list_incidents as _list_incidents,
    update_incident as _update_incident,
    update_incident_status as _update_incident_status,
)
from services.brasaland_api.incidents_models import (
    VALID_STATE_TRANSITIONS,
)

_logger = logging.getLogger("brasaland-mcp.tools.incidents")

# Scopes que necesita cada tool (se validan en la capa de auth)
SCOPE_INCIDENTS_READ = "incidents:read"
SCOPE_INCIDENTS_WRITE = "incidents:write"


# ---------------------------------------------------------------------------
# Tools de solo lectura
# ---------------------------------------------------------------------------

def list_incidents_tool(
    estado: str | None = None,
    local_id: str | None = None,
    categoria: str | None = None,
    origen: str | None = None,
    prioridad: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> list[dict[str, Any]]:
    """Lista incidencias con filtros opcionales.

    Args:
        estado: Filtrar por estado (abierta, en_progreso, resuelta, descartada)
        local_id: Filtrar por local (L01-L14)
        categoria: Filtrar por categoría (queja, solicitud, fallo_operativo)
        origen: Filtrar por origen (cliente, interno)
        prioridad: Filtrar por prioridad (baja, media, alta, critica)
        desde: Fecha ISO desde (YYYY-MM-DD)
        hasta: Fecha ISO hasta (YYYY-MM-DD)

    Returns:
        Lista de incidencias que coinciden con los filtros.

    Errors:
        -32602: Si los parámetros de filtro no son válidos.
    """
    try:
        result = _list_incidents(
            estado=estado,
            local_id=local_id,
            categoria=categoria,
            origen=origen,
            prioridad=prioridad,
            desde=desde,
            hasta=hasta,
        )
        _logger.info("list_incidents_tool -> %d resultados (filtros: %s)", len(result), _filtros_str(
            estado=estado, local_id=local_id, categoria=categoria, origen=origen,
            prioridad=prioridad, desde=desde, hasta=hasta,
        ))
        return result
    except Exception as exc:
        _logger.error("list_incidents_tool falló: %s", exc)
        raise


def get_incident_tool(incident_id: int) -> dict[str, Any] | None:
    """Obtiene una incidencia por su ID numérico.

    Args:
        incident_id: ID numérico de la incidencia (doc_id en TinyDB)

    Returns:
        Datos de la incidencia o None si no existe.

    Errors:
        -32602: Si incident_id no es un entero positivo.
    """
    if not isinstance(incident_id, int) or incident_id < 1:
        raise ValueError("incident_id debe ser un entero positivo.")
    try:
        result = _get_incident(incident_id)
        _logger.info("get_incident_tool(%d) -> %s", incident_id, "encontrada" if result else "no encontrada")
        return result
    except Exception as exc:
        _logger.error("get_incident_tool(%d) falló: %s", incident_id, exc)
        raise


def get_incidents_summary_tool() -> dict[str, Any]:
    """Obtiene un resumen estadístico de todas las incidencias.

    Returns:
        Diccionario con total, agrupaciones por estado, categoría, prioridad y origen.
    """
    try:
        result = _get_incidents_summary()
        _logger.info("get_incidents_summary_tool -> total=%d", result.get("total", 0))
        return result
    except Exception as exc:
        _logger.error("get_incidents_summary_tool falló: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Tools de escritura (requieren scope incidents:write)
# ---------------------------------------------------------------------------

def create_incident_tool(
    title: str,
    description: str,
    fecha_reporte: str,
    local_id: str,
    origen: str,
    categoria: str,
    prioridad: str,
    cliente_id: str | None = None,
    cliente_email: str | None = None,
    cliente_telefono: str | None = None,
) -> dict[str, Any]:
    """Crea una nueva incidencia en el sistema.

    Args:
        title: Título de la incidencia (1-200 caracteres)
        description: Descripción detallada (1-2000 caracteres)
        fecha_reporte: Fecha del reporte en formato ISO (YYYY-MM-DD)
        local_id: Código del local (L01-L14)
        origen: Origen de la incidencia (cliente, interno)
        categoria: Categoría (queja, solicitud, fallo_operativo)
        prioridad: Nivel de prioridad (baja, media, alta, critica)
        cliente_id: Identificador opcional del cliente
        cliente_email: Email opcional del cliente
        cliente_telefono: Teléfono opcional del cliente

    Returns:
        La incidencia creada con su ID y estado inicial "abierta".

    Errors:
        -32602: Si algún parámetro no cumple las validaciones de dominio
                (local_id inválido, categoría incorrecta, etc.).
    """
    payload = {
        "title": title,
        "description": description,
        "fecha_reporte": fecha_reporte,
        "local_id": local_id,
        "origen": origen,
        "categoria": categoria,
        "prioridad": prioridad,
        "cliente_id": cliente_id,
        "cliente_email": cliente_email,
        "cliente_telefono": cliente_telefono,
    }
    try:
        result = _create_incident(payload)
        incident_id = result.get("incident_id", "?")
        _logger.info("create_incident_tool -> creada %s", incident_id)
        return result
    except Exception as exc:
        _logger.error("create_incident_tool falló: %s", exc)
        raise


def update_incident_tool(
    incident_id: int,
    title: str | None = None,
    description: str | None = None,
    local_id: str | None = None,
    origen: str | None = None,
    categoria: str | None = None,
    prioridad: str | None = None,
    cliente_id: str | None = None,
    cliente_email: str | None = None,
    cliente_telefono: str | None = None,
) -> dict[str, Any] | None:
    """Actualiza los campos de una incidencia existente.

    Args:
        incident_id: ID numérico de la incidencia a actualizar
        title: Nuevo título (opcional)
        description: Nueva descripción (opcional)
        local_id: Nuevo código de local (opcional)
        origen: Nuevo origen (opcional)
        categoria: Nueva categoría (opcional)
        prioridad: Nueva prioridad (opcional)
        cliente_id: Nuevo ID de cliente (opcional)
        cliente_email: Nuevo email de cliente (opcional)
        cliente_telefono: Nuevo teléfono de cliente (opcional)

    Returns:
        La incidencia actualizada o None si no existe.

    Errors:
        -32602: Si incident_id no es un entero positivo o los campos no son válidos.
    """
    if not isinstance(incident_id, int) or incident_id < 1:
        raise ValueError("incident_id debe ser un entero positivo.")
    updates = {
        k: v for k, v in {
            "title": title,
            "description": description,
            "local_id": local_id,
            "origen": origen,
            "categoria": categoria,
            "prioridad": prioridad,
            "cliente_id": cliente_id,
            "cliente_email": cliente_email,
            "cliente_telefono": cliente_telefono,
        }.items() if v is not None
    }
    try:
        if not updates:
            _logger.info("update_incident_tool(%d) -> sin cambios", incident_id)
            return _get_incident(incident_id)
        result = _update_incident(incident_id, updates)
        _logger.info("update_incident_tool(%d) -> %s", incident_id, "actualizada" if result else "no encontrada")
        return result
    except Exception as exc:
        _logger.error("update_incident_tool(%d) falló: %s", incident_id, exc)
        raise


def update_incident_status_tool(incident_id: int, nuevo_estado: str) -> dict[str, Any] | None:
    """Cambia el estado de una incidencia siguiendo la máquina de estados.

    Transiciones válidas:
      - abierta → en_progreso, descartada
      - en_progreso → resuelta, descartada
      - resuelta → (ninguna, estado terminal)
      - descartada → (ninguna, estado terminal)

    Args:
        incident_id: ID numérico de la incidencia
        nuevo_estado: Estado destino (abierta, en_progreso, resuelta, descartada)

    Returns:
        La incidencia actualizada o None si no existe.

    Raises:
        ValueError: Si la transición de estado no es válida (código -32602).

    Errors:
        -32602: Si incident_id no es positivo, el estado es inválido o la
                transición no está permitida por la máquina de estados.
    """
    if not isinstance(incident_id, int) or incident_id < 1:
        raise ValueError("incident_id debe ser un entero positivo.")
    estados_validos = {"abierta", "en_progreso", "resuelta", "descartada"}
    if nuevo_estado not in estados_validos:
        raise ValueError(
            f"Estado inválido: '{nuevo_estado}'. "
            f"Valores permitidos: {', '.join(sorted(estados_validos))}."
        )
    try:
        result = _update_incident_status(incident_id, nuevo_estado)
        _logger.info(
            "update_incident_status_tool(%d, %s) -> %s",
            incident_id, nuevo_estado,
            "actualizada" if result else "no encontrada",
        )
        return result
    except ValueError:
        raise
    except Exception as exc:
        _logger.error("update_incident_status_tool(%d, %s) falló: %s", incident_id, nuevo_estado, exc)
        raise


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _filtros_str(**kwargs: Any) -> str:
    """Convierte filtros a string legible para logs, omitiendo None."""
    partes = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    return ", ".join(partes) if partes else "sin filtros"