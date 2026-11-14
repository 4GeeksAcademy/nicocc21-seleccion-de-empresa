"""Cliente MCP reutilizable para el servidor Brasaland MCP.

Proporciona una interfaz async robusta para conectar con el MCP Server
de Brasaland a través del transporte Streamable HTTP con autenticación
OAuth 2.1 (client_credentials).

Uso típico desde un agente::

    async with BrasalandMCPClient() as client:
        tools = await client.list_tools()
        result = await client.call_tool("list_incidents", {"estado": "abierta"})

Requiere las variables de entorno:
    MCP_SERVER_URL   — URL del servidor MCP (ej: http://localhost:8081/mcp)
    MCP_CLIENT_ID    — Client ID para OAuth (opcional, default "brasaland-agent")
    MCP_CLIENT_SECRET — Client secret para OAuth (opcional)
    MCP_TOKEN        — Token JWT directamente (opcional, salta OAuth)
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuración por defecto
# ---------------------------------------------------------------------------
DEFAULT_MCP_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp")
DEFAULT_CLIENT_ID = os.getenv("MCP_CLIENT_ID", "brasaland-agent")
DEFAULT_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "")
DIRECT_TOKEN = os.getenv("MCP_TOKEN", "")


# ---------------------------------------------------------------------------
# Utilidades OAuth 2.1 — client_credentials grant
# ---------------------------------------------------------------------------
async def _fetch_client_credentials_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    scopes: list[str] | None = None,
) -> str:
    """Solicita un token JWT vía client_credentials al Authorization Server."""
    import httpx

    scope_str = " ".join(scopes) if scopes else "incidents:read incidents:write inventory:read"

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope_str,
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(token_url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"OAuth response missing access_token: {data}")
        return token


# ---------------------------------------------------------------------------
# Contexto de sesión devuelto al usuario
# ---------------------------------------------------------------------------
class MCPSession:
    """Mantiene la sesión activa con el servidor MCP.

    No se instancia directamente; se obtiene del context manager
    ``BrasalandMCPClient``.
    """

    def __init__(self, tools: list[dict[str, Any]], call_tool_fn):
        self._tools = tools
        self._call_tool_fn = call_tool_fn

    @property
    def tools(self) -> list[dict[str, Any]]:
        """Lista de herramientas disponibles con sus metadatos."""
        return list(self._tools)

    def get_tool_names(self) -> list[str]:
        """Nombres de todas las herramientas registradas."""
        return [t["name"] for t in self._tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Invoca una herramienta del MCP Server y devuelve el texto de respuesta.

        Args:
            name: Nombre exacto de la herramienta (ej. ``list_incidents``).
            arguments: Diccionario con los argumentos de la herramienta.

        Returns:
            Contenido textual de la respuesta. Si hay error, el texto
            comienza con ``ERROR:``.
        """
        return await self._call_tool_fn(name, arguments)


# ---------------------------------------------------------------------------
# Context manager principal
# ---------------------------------------------------------------------------
@asynccontextmanager
async def BrasalandMCPClient(
    server_url: str | None = None,
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    token: str | None = None,
    token_url: str | None = None,
) -> AsyncGenerator[MCPSession, None]:
    """Conecta al servidor MCP de Brasaland y devuelve una sesión lista.

    Estrategia de autenticación (por orden de precedencia):

    1. Si se pasa ``token`` directamente, se usa ese JWT.
    2. Si no, se hace un grant ``client_credentials`` contra el token
       endpoint de OAuth usando ``client_id`` + ``client_secret``.
    3. Si no hay credenciales, se conecta sin token (solo útil en
       desarrollo sin autenticación).

    Args:
        server_url: URL del servidor MCP (ej. ``http://localhost:8081/mcp``).
        client_id: Client ID OAuth.
        client_secret: Client secret OAuth.
        token: Token JWT directo (opcional).
        token_url: URL del token endpoint OAuth (ej.
            ``http://localhost:8080/token``). Por defecto se deriva de
            ``OAUTH_ISSUER``.

    Yields:
        :class:`MCPSession` lista para usar.
    """
    # --- Resolver parámetros -------------------------------------------------
    url = server_url or DEFAULT_MCP_URL
    cid = client_id or DEFAULT_CLIENT_ID
    csecret = client_secret or DEFAULT_CLIENT_SECRET
    bearer_token = token or DIRECT_TOKEN

    # --- Obtener token si no vino directo ------------------------------------
    if not bearer_token and csecret:
        issuer = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
        tok_url = token_url or f"{issuer}/token"
        logger.info("Solicitando token OAuth client_credentials para %s", cid)
        bearer_token = await _fetch_client_credentials_token(tok_url, cid, csecret)

    # --- Construir cliente HTTP con o sin auth -------------------------------
    from mcp import ClientSession
    from mcp.client.streamable_http import (
        create_mcp_http_client,
        streamable_http_client,
    )

    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    http_client = create_mcp_http_client(headers=headers)

    async with http_client:
        try:
            async with streamable_http_client(url, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    # --- Inicializar sesión ----------------------------------
                    await session.initialize()
                    logger.info("Conectado al MCP Server: %s", url)

                    # --- Listar herramientas disponibles ---------------------
                    tools_result = await session.list_tools()
                    tools_list = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": t.input_schema,
                        }
                        for t in tools_result.tools
                    ]
                    logger.info("MCP Server expone %d tools", len(tools_list))

                    # --- Wrapper para call_tool ------------------------------
                    async def _call_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
                        result = await session.call_tool(name, arguments)
                        if result.is_error:
                            texts = [
                                c.text
                                for c in result.content
                                if hasattr(c, "text") and c.text
                            ]
                            error_msg = texts[0] if texts else f"Error invocando {name}"
                            return f"ERROR: {error_msg}"

                        texts = [
                            c.text
                            for c in result.content
                            if hasattr(c, "text") and c.text
                        ]
                        return "\n".join(texts) if texts else "(sin contenido)"

                    yield MCPSession(tools=tools_list, call_tool_fn=_call_tool)

        except Exception as exc:
            logger.error("Error conectando al MCP Server %s: %s", url, exc)
            raise


# ---------------------------------------------------------------------------
# Función helper para uso rápido desde scripts/CLI
# ---------------------------------------------------------------------------
async def quick_call(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    server_url: str | None = None,
    token: str | None = None,
) -> str:
    """Conecta rápido al MCP, llama a una herramienta y devuelve el resultado.

    Ejemplo::

        result = await quick_call("list_incidents", {"estado": "abierta"})
    """
    async with BrasalandMCPClient(server_url=server_url, token=token) as session:
        return await session.call_tool(tool_name, arguments)