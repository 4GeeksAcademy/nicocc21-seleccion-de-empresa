"""Configuración del Support Agent.

Lee las mismas variables de entorno que el MCP Server,
permitiendo que el agente se configure automáticamente.
Incluye configuración del subsistema de memoria episódica.
"""

from __future__ import annotations

import os

# ── MCP / OAuth ──────────────────────────────
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp")
MCP_CLIENT_ID = os.getenv("MCP_CLIENT_ID", "brasaland-agent")
MCP_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "")
OAUTH_ISSUER = os.getenv("OAUTH_ISSUER", "http://localhost:8080")
MCP_LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO")

# ── Memory subsystem ─────────────────────────
MEMORY_STORE_DIR = os.getenv("MEMORY_STORE_DIR", "data/memory")
MEMORY_DEFAULT_LANGUAGE = os.getenv("MEMORY_DEFAULT_LANGUAGE", "es")
MEMORY_EVALUATION_THRESHOLD = float(
    os.getenv("MEMORY_EVALUATION_THRESHOLD", "0.4")
)
MEMORY_CLASSIFICATION_THRESHOLD = float(
    os.getenv("MEMORY_CLASSIFICATION_THRESHOLD", "0.5")
)
MEMORY_PROPOSAL_TTL_MINUTES = int(
    os.getenv("MEMORY_PROPOSAL_TTL_MINUTES", "30")
)
MEMORY_MIN_ENTRIES_FOR_CONSOLIDATION = int(
    os.getenv("MEMORY_MIN_ENTRIES_FOR_CONSOLIDATION", "2")
)
MEMORY_AUTO_CONSOLIDATE = (
    os.getenv("MEMORY_AUTO_CONSOLIDATE", "true").lower() == "true"
)