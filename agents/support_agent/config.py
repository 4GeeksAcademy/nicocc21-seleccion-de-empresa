"""Configuración del Support Agent.

Lee las mismas variables de entorno que el MCP Server,
permitiendo que el agente se configure automáticamente.
"""

from __future__ import annotations

import os

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp")
MCP_CLIENT_ID = os.getenv("MCP_CLIENT_ID", "brasaland-agent")
MCP_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "")
OAUTH_ISSUER = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")