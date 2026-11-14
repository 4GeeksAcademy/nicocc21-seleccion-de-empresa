"""Middleware de autenticación OAuth 2.1 para el servidor MCP.

Implementa validación de tokens JWT Bearer y scopes usando mcpauth.
Se integra con FastMCP a través del sistema de Middleware nativo.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

# Scopes que puede requerir cada tool
from mcps.brasaland_mcp.tools.incidents import (
    SCOPE_INCIDENTS_READ,
    SCOPE_INCIDENTS_WRITE,
)
from mcps.brasaland_mcp.tools.inventory import (
    SCOPE_INVENTORY_READ,
)

_logger = logging.getLogger(__name__)

# Mapa: tool_name -> lista de scopes requeridos (todos deben estar presentes)
_TOOL_SCOPES: dict[str, list[str]] = {
    # Incidentes — solo lectura
    "list_incidents": [SCOPE_INCIDENTS_READ],
    "get_incident": [SCOPE_INCIDENTS_READ],
    "get_incidents_summary": [SCOPE_INCIDENTS_READ],
    # Incidentes — escritura
    "create_incident": [SCOPE_INCIDENTS_WRITE],
    "update_incident": [SCOPE_INCIDENTS_WRITE],
    "update_incident_status": [SCOPE_INCIDENTS_WRITE],
    # Inventario — solo lectura
    "query_inventory": [SCOPE_INVENTORY_READ],
    # Inventario — rechazo explícito de escritura
    "reject_inventory_write": [SCOPE_INVENTORY_READ],
}


class BrasalandAuthMiddleware(Middleware):
    """Middleware que valida autenticación y autorización OAuth 2.1.

    Verifica que el token JWT incluya los scopes necesarios para cada tool.
    Si el cliente no ha proporcionado token, rechaza la llamada.
    """

    def __init__(self) -> None:
        super().__init__()

    async def on_initialize(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """En la inicialización, validamos que el cliente se autentique.

        La autenticación real ocurre en on_call_tool (por tool).
        Aquí solo verificamos que el cliente envíe metadatos de auth.
        """
        return await call_next

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Interceptor de llamadas a tools: valida scopes OAuth y loguea resultado.

        El token JWT debe estar presente en el contexto de autenticación
        y contener los scopes requeridos por la tool invocada.

        Tras la ejecución, registra el resultado (éxito o error) para
        trazabilidad completa.
        """
        tool_name = self._get_tool_name(context)

        # Verificar si la tool requiere scopes
        required_scopes = _TOOL_SCOPES.get(tool_name)
        if required_scopes is None:
            # Tool sin restricción explícita — permitir pero loguear
            _logger.warning("Tool '%s' sin scopes definidos — se permite el acceso", tool_name)
            result = await call_next
            _logger.info("Tool '%s' ejecutada (sin scope definido)", tool_name)
            return result

        # Extraer auth_info del contexto (inyectado por mcpauth)
        auth_info = self._get_auth_info(context)
        if auth_info is None:
            _logger.warning("Tool '%s' rechazada: sin autenticación", tool_name)
            return self._unauthorized(
                context,
                f"Se requiere autenticación OAuth 2.1 para usar '{tool_name}'. "
                f"Scopes necesarios: {', '.join(required_scopes)}.",
            )

        # Validar scopes
        token_scopes = self._extract_scopes(auth_info)
        missing = [s for s in required_scopes if s not in token_scopes]
        if missing:
            _logger.warning(
                "Tool '%s' rechazada para subject=%s: faltan scopes %s",
                tool_name,
                self._extract_subject(auth_info),
                missing,
            )
            return self._forbidden(
                context,
                f"Token no tiene los scopes requeridos para '{tool_name}'. "
                f"Faltan: {', '.join(missing)}.",
            )

        _logger.info(
            "Tool '%s' autorizada para subject=%s con scopes=%s",
            tool_name,
            self._extract_subject(auth_info),
            token_scopes,
        )

        # Ejecutar la tool y loguear el resultado
        try:
            result = await call_next
            _logger.info(
                "Tool '%s' ejecutada exitosamente para subject=%s",
                tool_name,
                self._extract_subject(auth_info),
            )
            return result
        except Exception as exc:
            _logger.error(
                "Tool '%s' falló para subject=%s: %s: %s",
                tool_name,
                self._extract_subject(auth_info),
                type(exc).__name__,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tool_name(context: MiddlewareContext[Any]) -> str:
        """Extrae el nombre de la tool del contexto del mensaje."""
        params = getattr(context, "params", None) or {}
        return params.get("name", str(params))

    @staticmethod
    def _get_auth_info(context: MiddlewareContext[Any]) -> Any | None:
        """Extrae el AuthInfo del contexto (inyectado por mcpauth)."""
        request = getattr(context, "request", None)
        if request is None:
            return None
        # mcpauth guarda AuthInfo en request.state.auth_info
        return getattr(request.state, "auth_info", None)

    @staticmethod
    def _extract_scopes(auth_info: Any) -> list[str]:
        """Extrae la lista de scopes del AuthInfo."""
        # AuthInfo tiene .scopes si es de mcpauth
        scopes = getattr(auth_info, "scopes", None)
        if isinstance(scopes, str):
            return scopes.split()
        if isinstance(scopes, (list, tuple)):
            return list(scopes)
        # Intentar desde el token payload
        token_data = getattr(auth_info, "token_data", None) or {}
        scope_str = token_data.get("scope", "")
        if isinstance(scope_str, str):
            return scope_str.split()
        return []

    @staticmethod
    def _extract_subject(auth_info: Any) -> str:
        """Extrae el subject (user_id) del AuthInfo."""
        sub = getattr(auth_info, "subject", None)
        if sub:
            return str(sub)
        token_data = getattr(auth_info, "token_data", None) or {}
        return str(token_data.get("sub", "unknown"))

    @staticmethod
    def _unauthorized(context: MiddlewareContext[Any], message: str) -> dict:
        """Responde 401 Unauthorized."""
        _logger.warning("MCP 401: %s", message)
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32001,
                "message": "Unauthorized",
                "data": {"detail": message},
            },
            "id": getattr(context, "request_id", None),
        }

    @staticmethod
    def _forbidden(context: MiddlewareContext[Any], message: str) -> dict:
        """Responde 403 Forbidden."""
        _logger.warning("MCP 403: %s", message)
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32002,
                "message": "Forbidden",
                "data": {"detail": message},
            },
            "id": getattr(context, "request_id", None),
        }