"""Configuración centralizada del MCP Server.

Toda la configuración sensible se lee desde variables de entorno
con valores por defecto razonables para desarrollo local.
"""

from __future__ import annotations

import os
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# -- Rutas del monorepo -----------------------------------------------
MONOREPO_ROOT = Path(__file__).resolve().parents[2]
INCIDENTS_DB_PATH = MONOREPO_ROOT / "services" / "brasaland_api" / "data" / "incidents.json"

# -- Servidor HTTP (Streamable HTTP) ----------------------------------
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8081"))

# -- OAuth / MCP Auth (mcpauth) ---------------------------------------
# Clave pública del Authorization Server (JWKS endpoint) para validar tokens.
# En producción apunta al issuer real; en desarrollo se puede usar una
# clave simétrica inline (solo para testing).
OAUTH_ISSUER = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
OAUTH_JWKS_URL = os.getenv("OAUTH_JWKS_URL", f"{OAUTH_ISSUER}/.well-known/jwks.json")

# Secret compartido para validación HMAC en desarrollo.
# En producción se usa JWKS asimétrica; esto es solo fallback.
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "dev-secret-change-in-prod")

# -- Scopes definidos --------------------------------------------------
# Cada scope sigue el principio de mínimo privilegio.
SCOPE_INCIDENTS_READ = "incidents:read"
SCOPE_INCIDENTS_WRITE = "incidents:write"
SCOPE_INVENTORY_READ = "inventory:read"

# -- Bases de datos externas -------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

# -- Modo desarrollo (saltar autenticación) ---------------------------
# En producción esto debe estar en False (o no definido).
# En desarrollo/testing (MCP Playground) se puede poner en True para
# saltar la validación de tokens JWT.
AUTH_DISABLED = _bool(os.getenv("MCP_AUTH_DISABLED"), default=False)

# -- Logging -----------------------------------------------------------
LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")