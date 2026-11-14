"""Support Agent — Brasaland.

Agente conversacional para atención postventa que consume el MCP Server
de Brasaland a través del cliente reutilizable ``BrasalandMCPClient``.

Modos de uso:
    1. Como biblioteca — importa ``SupportAgent`` desde código Python.
    2. Como CLI interactiva — ejecuta ``python -m agents.support_agent.agent``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from mcps.brasaland_mcp.client import (
    BrasalandMCPClient,
    MCPSession,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agente de soporte
# ---------------------------------------------------------------------------
class SupportAgent:
    """Agente que gestiona incidencias a través del MCP Server de Brasaland.

    Args:
        server_url: URL del MCP Server (opcional, default de env var).
        client_id: Client ID OAuth.
        client_secret: Client secret OAuth.
        token: Token JWT directo (opcional).
    """

    def __init__(
        self,
        server_url: str | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        token: str | None = None,
    ) -> None:
        self._server_url = server_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = token
        self._session: MCPSession | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    async def __aenter__(self) -> SupportAgent:
        self._cm = BrasalandMCPClient(
            self._server_url,
            client_id=self._client_id,
            client_secret=self._client_secret,
            token=self._token,
        )
        self._session = await self._cm.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(*args)

    # ------------------------------------------------------------------
    # Propiedades delegadas a la sesión MCP
    # ------------------------------------------------------------------
    @property
    def tools(self) -> list[dict[str, Any]]:
        """Lista de herramientas disponibles."""
        if self._session is None:
            raise RuntimeError("Agent not connected. Use 'async with SupportAgent()'")
        return self._session.tools

    def get_tool_names(self) -> list[str]:
        """Nombres de herramientas registradas en el MCP Server."""
        if self._session is None:
            raise RuntimeError("Agent not connected. Use 'async with SupportAgent()'")
        return self._session.get_tool_names()

    # ------------------------------------------------------------------
    # Métodos de alto nivel para incidencias
    # ------------------------------------------------------------------
    async def list_incidents(self, **filters: Any) -> str:
        """Lista incidencias con filtros opcionales.

        Args:
            **filters: estado, local_id, categoria, origen, prioridad,
                fecha_desde, fecha_hasta.
        """
        return await self._call("list_incidents_tool", filters)

    async def get_incident(self, incident_id: int) -> str:
        """Obtiene una incidencia por su ID."""
        return await self._call("get_incident_tool", {"incident_id": incident_id})

    async def get_summary(self) -> str:
        """Resumen estadístico de todas las incidencias."""
        return await self._call("get_incidents_summary_tool", {})

    async def create_incident(
        self,
        title: str,
        description: str,
        fecha_reporte: str,
        local_id: str,
        origen: str,
        categoria: str,
        prioridad: str,
    ) -> str:
        """Crea una nueva incidencia."""
        return await self._call(
            "create_incident_tool",
            {
                "title": title,
                "description": description,
                "fecha_reporte": fecha_reporte,
                "local_id": local_id,
                "origen": origen,
                "categoria": categoria,
                "prioridad": prioridad,
            },
        )

    async def update_incident(self, incident_id: int, **fields: Any) -> str:
        """Actualiza campos editables de una incidencia."""
        payload = {"incident_id": incident_id, **fields}
        return await self._call("update_incident_tool", payload)

    async def update_status(self, incident_id: int, nuevo_estado: str) -> str:
        """Cambia el estado de una incidencia."""
        return await self._call(
            "update_incident_status_tool",
            {"incident_id": incident_id, "nuevo_estado": nuevo_estado},
        )

    async def query_inventory(self, **filters: Any) -> str:
        """Consulta ingredientes del inventario (solo lectura)."""
        return await self._call("query_inventory", filters or None)

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------
    async def _call(self, tool_name: str, arguments: dict[str, Any] | None) -> str:
        if self._session is None:
            raise RuntimeError("Agent not connected. Use 'async with SupportAgent()'")
        return await self._session.call_tool(tool_name, arguments)


# ---------------------------------------------------------------------------
# CLI interactiva
# ---------------------------------------------------------------------------
def _print_help(tools: list[dict[str, Any]]) -> None:
    print("\nComandos disponibles:")
    print("  help                    — Muestra esta ayuda")
    print("  tools                   — Lista herramientas del MCP Server")
    print("  list [filtros...]       — Lista incidencias (ej: list estado=abierta)")
    print("  get <id>                — Obtiene incidencia por ID")
    print("  summary                 — Resumen estadístico")
    print("  create                  — Crea nueva incidencia (asistido)")
    print("  update <id> <campo>=<v> — Actualiza campo (ej: update 1 titulo=Nuevo)")
    print("  status <id> <estado>    — Cambia estado (ej: status 1 en_progreso)")
    print("  inventory [filtros...]  — Consulta inventario (solo lectura)")
    print("  exit / quit             — Salir")
    print()


async def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="Support Agent CLI — Brasaland MCP")
    parser.add_argument("--url", help="URL del MCP Server")
    parser.add_argument("--token", help="Token JWT directo")
    args = parser.parse_args()

    print("=== Support Agent CLI — Brasaland ===")
    print("Conectando al MCP Server...")

    try:
        async with SupportAgent(server_url=args.url, token=args.token) as agent:
            print(f"✅ Conectado. Tools disponibles: {len(agent.tools)}")
            _print_help(agent.tools)

            while True:
                try:
                    raw = input("\n❯ ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nAdiós.")
                    break

                if not raw:
                    continue

                parts = raw.split()
                cmd = parts[0].lower()

                if cmd in ("exit", "quit"):
                    break
                elif cmd == "help":
                    _print_help(agent.tools)
                elif cmd == "tools":
                    print(f"\nTools ({len(agent.tools)}):")
                    for t in agent.tools:
                        print(f"  • {t['name']}: {t['description'][:70]}")
                elif cmd == "list":
                    filters = {}
                    for f in parts[1:]:
                        if "=" in f:
                            k, v = f.split("=", 1)
                            filters[k] = v
                    result = await agent.list_incidents(**filters)
                    print(result)
                elif cmd == "get":
                    if len(parts) < 2:
                        print("Uso: get <incident_id>")
                        continue
                    result = await agent.get_incident(int(parts[1]))
                    print(result)
                elif cmd == "summary":
                    result = await agent.get_summary()
                    print(result)
                elif cmd == "create":
                    print("=== Crear incidencia ===")
                    title = input("  Title: ").strip()
                    desc = input("  Description: ").strip()
                    fecha_reporte = input("  Fecha reporte (YYYY-MM-DD): ").strip()
                    local_id = input("  Local ID (L01-L14): ").strip()
                    origen = input("  Origen (cliente/interno): ").strip()
                    cat = input("  Categoría (queja/solicitud/fallo_operativo): ").strip()
                    prio = input("  Prioridad (baja/media/alta/critica): ").strip()
                    result = await agent.create_incident(
                        title, desc, fecha_reporte, local_id, origen, cat, prio
                    )
                    print(result)
                elif cmd == "update":
                    if len(parts) < 3:
                        print("Uso: update <id> <campo>=<valor>")
                        continue
                    iid = int(parts[1])
                    fields = {}
                    for f in parts[2:]:
                        if "=" in f:
                            k, v = f.split("=", 1)
                            fields[k] = v
                    result = await agent.update_incident(iid, **fields)
                    print(result)
                elif cmd == "status":
                    if len(parts) < 3:
                        print("Uso: status <id> <nuevo_estado>")
                        continue
                    result = await agent.update_status(int(parts[1]), parts[2])
                    print(result)
                elif cmd == "inventory":
                    filters = {}
                    for f in parts[1:]:
                        if "=" in f:
                            k, v = f.split("=", 1)
                            filters[k] = v
                    result = await agent.query_inventory(**filters)
                    print(result)
                else:
                    print(f"Comando desconocido: {cmd}. Escribe 'help' para ayuda.")
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(_run_cli())