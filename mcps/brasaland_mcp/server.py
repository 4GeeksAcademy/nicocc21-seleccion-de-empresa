#!/usr/bin/env python3
"""Brasaland MCP Server — Streamable HTTP con OAuth 2.1.

Servidor MCP independiente que expone las tools de Incidents Manager
e Inventory como tools protegidas por OAuth 2.1 / OIDC.

Transporte: Streamable HTTP sobre uvicorn.
Auth: MCP Auth (mcpauth) como resource server OAuth 2.1.

Uso:
    uv run python -m mcps.brasaland_mcp.server
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Asegurar que el monorepo root está en sys.path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

# Cargar .env del backend (para DATABASE_URL y demás)
_env_path = _ROOT / "services" / "brasaland_api" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Cargar .env específico de MCP (primero mcp, fallback a mcp.example)
for _mcp_candidate in ("mcp", "mcp.example"):
    _mcp_env_path = _ROOT / "env" / _mcp_candidate
    if _mcp_env_path.exists():
        load_dotenv(_mcp_env_path)
        break

from fastmcp import FastMCP
from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthorizationServerMetadata, AuthServerType
from starlette.types import ASGIApp

from mcps.brasaland_mcp import config
from mcps.brasaland_mcp.middleware import BrasalandAuthMiddleware
from mcps.brasaland_mcp.tools import incidents as incidents_tools
from mcps.brasaland_mcp.tools import inventory as inventory_tools

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
_logger = logging.getLogger("brasaland-mcp")

# ---------------------------------------------------------------------------
# FastMCP App
# ---------------------------------------------------------------------------

def create_server() -> FastMCP:
    """Crea y configura la instancia FastMCP con todas las tools y auth."""

    server = FastMCP(
        name="Brasaland MCP Server",
        version="0.1.0",
        instructions=(
            "Para usar este servidor, autentícate con OAuth 2.1 usando "
            "el flujo client_credentials con los scopes adecuados.\n\n"
            "Tools disponibles:\n"
            "  - incidents:* → Gestión de tickets (requiere incidents:read o incidents:write)\n"
            "  - inventory:* → Consulta de inventario solo lectura (requiere inventory:read)"
        ),
    )

    # ------------------------------------------------------------------
    # Registrar tools de Incidents Manager
    # ------------------------------------------------------------------
    server.add_tool(incidents_tools.list_incidents_tool)
    server.add_tool(incidents_tools.get_incident_tool)
    server.add_tool(incidents_tools.get_incidents_summary_tool)
    server.add_tool(incidents_tools.create_incident_tool)
    server.add_tool(incidents_tools.update_incident_tool)
    server.add_tool(incidents_tools.update_incident_status_tool)

    # ------------------------------------------------------------------
    # Registrar tools de Inventory (solo lectura)
    # ------------------------------------------------------------------
    server.add_tool(inventory_tools.query_inventory)
    server.add_tool(inventory_tools.reject_inventory_write)

    return server


# ---------------------------------------------------------------------------
# Configuración OAuth 2.1 con MCP Auth
# ---------------------------------------------------------------------------

def create_oauth_config() -> AuthServerConfig:
    """Crea la configuración del Authorization Server para mcpauth."""
    return AuthServerConfig(
        metadata=AuthorizationServerMetadata(
            issuer=config.OAUTH_ISSUER,
            authorization_endpoint=f"{config.OAUTH_ISSUER}/authorize",
            token_endpoint=f"{config.OAUTH_ISSUER}/token",
            jwks_uri=config.OAUTH_JWKS_URL,
            response_types_supported=["code"],
            grant_types_supported=["client_credentials", "authorization_code"],
            response_modes_supported=["query", "fragment"],
            token_endpoint_auth_methods_supported=["client_secret_basic"],
            code_challenge_methods_supported=["S256"],
            scope_supported=[
                config.SCOPE_INCIDENTS_READ,
                config.SCOPE_INCIDENTS_WRITE,
                config.SCOPE_INVENTORY_READ,
            ],
        ),
        type=AuthServerType.REMOTE,
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point del servidor MCP."""
    _logger.info("Inicializando Brasaland MCP Server...")
    _logger.info("OAuth Issuer: %s", config.OAUTH_ISSUER)

    server = create_server()

    # Configurar OAuth (solo si no está en modo desarrollo)
    if config.AUTH_DISABLED:
        mcpauth = None
    else:
        oauth_config = create_oauth_config()
        mcpauth = MCPAuth(server=oauth_config)

    # Crear middleware Bearer Token de mcpauth
    # Nota: mcpauth devuelve una clase BaseHTTPMiddleware, NO una instancia.
    # FastMCP.http_app() acepta list[ASGIMiddleware] en su parámetro middleware.
    # Como mcpauth retorna una clase (no instancia), la envolvemos en una
    # función factory o la instanciamos en el lugar adecuado.
    #
    # FastMCP v4 usa su propio sistema de Middleware (fastmcp.server.middleware.Middleware)
    # que es diferente de Starlette/ASGI middleware. Por eso NO pasamos mcpauth
    # al http_app, sino que usamos el middleware nativo de FastMCP para la lógica
    # de autorización (BrasalandAuthMiddleware) junto con la verificación JWT
    # que hacemos manualmente en el middleware.
    #
    # El middleware de mcpauth se aplica a nivel Starlette (ASGI) para validar
    # el token JWT, y BrasalandAuthMiddleware (FastMCP) valida los scopes por tool.

    # Añadir nuestro middleware de autorización (FastMCP nativo)
    # Solo cuando la autenticación está habilitada
    if not config.AUTH_DISABLED:
        server.add_middleware(BrasalandAuthMiddleware())

    _logger.info("Servidor listo. Escuchando en %s:%s", config.HOST, config.PORT)
    _logger.info("Transporte: Streamable HTTP")

    # Arrancar con uvicorn usando http_app
    import uvicorn

    # Obtener la app Starlette con streamable-http
    # NOTA: FastMCP.http_app() devuelve StarletteWithLifespan que es compatible ASGI3
    starlette_app = server.http_app(
        transport="streamable-http",
        path="/mcp",
    )

    # Agregamos CORS y auth middleware a nivel Starlette
    from starlette.middleware.cors import CORSMiddleware

    starlette_app = _wrap_with_middleware(starlette_app, mcpauth)

    uvicorn.run(
        starlette_app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )


def _wrap_with_middleware(app: ASGIApp, mcpauth: MCPAuth | None) -> ASGIApp:
    """Envuelve la app con los middlewares necesarios (CORS + OAuth).

    Aplica:
      1. CORS (permitir orígenes externos)
      2. mcpauth bearer token middleware (valida JWT) — solo si no está
         deshabilitado por MCP_AUTH_DISABLED=1.

    En modo desarrollo (MCP_AUTH_DISABLED=1) se salta mcpauth,
    permitiendo probar con MCP Playground sin token JWT.
    """
    from starlette.middleware.cors import CORSMiddleware

    if config.AUTH_DISABLED:
        # Modo desarrollo — solo CORS, sin mcpauth
        _logger.warning(
            "⚠️  MCP_AUTH_DISABLED=1 — autenticación deshabilitada. "
            "No usar en producción."
        )
        return CORSMiddleware(
            app,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=True,
        )

    # Middleware de mcpauth para validar tokens JWT
    # bearer_auth_middleware retorna una CLASE (type[BaseHTTPMiddleware]),
    # no una instancia. La instanciamos con los scopes requeridos a nivel
    # global (luego se refinan por tool en BrasalandAuthMiddleware).
    bearer_cls = mcpauth.bearer_auth_middleware(
        "jwt",
        audience="brasaland-mcp",
        required_scopes=None,  # Se valida por tool en BrasalandAuthMiddleware
        show_error_details=True,
    )

    # Instanciamos el middleware con la app y envolvemos con CORS
    return CORSMiddleware(
        bearer_cls(app),
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )


if __name__ == "__main__":
    main()