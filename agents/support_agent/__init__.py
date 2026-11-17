"""Support Agent — Brasaland.

Agente conversacional para atención postventa que consume el MCP Server
de Brasaland a través del cliente reutilizable ``BrasalandMCPClient``.
"""

from .agent import SupportAgent

__all__ = ["SupportAgent"]