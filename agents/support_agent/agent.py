"""Support Agent — Brasaland.

Agente conversacional para atención postventa que consume el MCP Server
de Brasaland a través del cliente reutilizable ``BrasalandMCPClient``.

Extiende el agente con memoria episódica (Hito 8 — Parte 1):
    - Evalúa interacciones para detectar hechos memorables
    - Propone al usuario "¿Quieres que recuerde esto?"
    - Procesa la decisión del usuario y persiste lo aprobado
    - Inyecta contexto de memoria en las conversaciones

NOTA: Este agente ahora DELEGA la lógica RAG y de memoria al grafo LangGraph
      definido en ``services/brasaland_api.agent``, que es la integración
      principal. Esta clase se mantiene como envoltura para la CLI y para
      interoperar con el MCP Client, pero las nuevas funcionalidades deben
      implementarse en el grafo LangGraph.

Modos de uso:
    1. Como biblioteca — importa ``SupportAgent`` desde código Python.
    2. Como CLI interactiva — ejecuta ``python -m agents.support_agent.agent``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any

from mcps.brasaland_mcp.client import (
    BrasalandMCPClient,
    MCPSession,
)

from . import config
from .memory.memory_manager import MemoryManager

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
        memory_enabled: Activar subsistema de memoria (default: True).
    """

    def __init__(
        self,
        server_url: str | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        token: str | None = None,
        memory_enabled: bool = True,
    ) -> None:
        self._server_url = server_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = token
        self._session: MCPSession | None = None

        # ── Memory subsystem ──────────────────────────────
        self._memory_enabled = memory_enabled
        self._memory: MemoryManager | None = None
        self._current_location_id: str = ""
        # Track the last proposal to correlate with user response
        self._last_proposal_id: str | None = None
        self._last_proposal_prompt: str | None = None

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

        # ── Initialize memory subsystem ──
        if self._memory_enabled:
            self._memory = MemoryManager(
                store=None,  # uses default path from config
            )
            logger.info(
                "Memory subsystem initialized (store=%s)",
                config.MEMORY_STORE_DIR,
            )

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
    # Memory subsystem — public API
    # ------------------------------------------------------------------
    @property
    def memory(self) -> MemoryManager:
        """Acceso al subsistema de memoria."""
        if self._memory is None:
            raise RuntimeError(
                "Memory subsystem disabled or not initialized. "
                "Set memory_enabled=True when constructing SupportAgent."
            )
        return self._memory

    def set_location(self, location_id: str) -> None:
        """Set the current location for memory context."""
        self._current_location_id = location_id

    def get_memory_context(self, location_id: str | None = None) -> str:
        """
        Get formatted memory context for the given (or current) location.

        Returns a string ready to inject into prompts, or empty string
        if memory is disabled or no memories exist.
        """
        if not self._memory_enabled or self._memory is None:
            return ""
        loc = location_id or self._current_location_id
        if not loc:
            return ""
        return self._memory.get_context(loc)

    async def evaluate_and_propose(
        self, interaction_text: str, location_id: str | None = None
    ) -> tuple[str | None, str | None]:
        """
        Evaluate an interaction for memorable content and propose to the user.

        Returns:
            Tuple of (proposal_id, confirmation_prompt) or (None, None).
        """
        if not self._memory_enabled or self._memory is None:
            return None, None

        loc = location_id or self._current_location_id
        if not loc:
            return None, None

        proposal, prompt = self._memory.evaluate_and_propose(
            interaction_text=interaction_text,
            location_id=loc,
            language=config.MEMORY_DEFAULT_LANGUAGE,
        )

        if proposal and prompt:
            self._last_proposal_id = proposal.id
            self._last_proposal_prompt = prompt
            return proposal.id, prompt

        return None, None

    async def process_memory_decision(
        self, user_response: str, proposal_id: str | None = None
    ) -> str:
        """
        Process a user's decision on a pending memory proposal.

        Args:
            user_response: The user's text response.
            proposal_id: The proposal to decide on. Uses last pending if None.

        Returns:
            A human-readable result message.
        """
        if not self._memory_enabled or self._memory is None:
            return ""

        pid = proposal_id or self._last_proposal_id
        if not pid:
            return "No hay una propuesta pendiente."

        try:
            decision, entry = self._memory.process_decision(
                proposal_id=pid,
                user_response=user_response,
                decided_by="user",
                language=config.MEMORY_DEFAULT_LANGUAGE,
            )

            self._last_proposal_id = None
            self._last_proposal_prompt = None

            if decision.decision.value == "accepted":
                return "✅ Entendido, lo recordaré para la próxima vez."
            elif decision.decision.value == "edited":
                return f"✅ Gracias, he guardado la corrección: {entry.content if entry else ''}"
            elif decision.decision.value == "rejected":
                return "❌ De acuerdo, no lo guardo."
            else:
                return "No he podido entender tu respuesta. Pregúntame de nuevo si quieres que recuerde algo."
        except ValueError as exc:
            logger.warning("Error processing memory decision: %s", exc)
            self._last_proposal_id = None
            self._last_proposal_prompt = None
            return "La propuesta ya no está disponible (puede haber expirado)."

    def has_pending_proposal(self) -> bool:
        """Check if there's a pending memory proposal awaiting user decision."""
        return self._last_proposal_id is not None

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
def _print_help() -> None:
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
    print("  --- Memoria ---")
    print("  location <id>           — Establece localización activa")
    print("  context [id]            — Muestra memoria de la localización")
    print("  memory info             — Estado del subsistema de memoria")
    print("  memory search <texto>   — Busca en la memoria")
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
            print("\n💡 Memory: agente con memoria episódica activada.")
            _print_help()

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
                    _print_help()
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

                # ── Memory commands ──
                elif cmd == "location":
                    if len(parts) < 2:
                        print("Uso: location <local_id> (ej: location L01)")
                        continue
                    agent.set_location(parts[1])
                    ctx = agent.get_memory_context()
                    print(f"📍 Localización activa: {parts[1]}")
                    if ctx:
                        print(f"\n{ctx}")
                    else:
                        print("  (No hay memorias para esta localización todavía.)")

                elif cmd == "context":
                    loc = parts[1] if len(parts) > 1 else None
                    ctx = agent.get_memory_context(loc)
                    if ctx:
                        print(ctx)
                    else:
                        loc_name = loc or agent._current_location_id or "(sin definir)"
                        print(f"No hay memorias para {loc_name}.")

                elif cmd == "memory":
                    sub = parts[1] if len(parts) > 1 else ""

                    if sub == "info":
                        info = agent.memory.get_store_info()
                        print("📊 Estado de la memoria:")
                        print(f"  Entradas activas:   {info['active_entries']}")
                        print(f"  Propuestas pendientes: {info['pending_proposals']}")
                        print(f"  Decisiones totales: {info['total_decisions']}")
                        print(f"  Consolidaciones:    {info['total_consolidations']}")
                        print(f"  Store version:      {info['store_version']}")

                    elif sub == "search" and len(parts) >= 3:
                        query = " ".join(parts[2:])
                        results = agent.memory.search_memories(query)
                        if results:
                            print(f"🔍 Resultados para '{query}':")
                            for r in results:
                                print(f"  • [{r.category.value}] {r.content}")
                                print(f"    Location: {r.location_id} | {r.created_at.strftime('%Y-%m-%d')}")
                        else:
                            print(f"No se encontraron resultados para '{query}'.")

                    else:
                        print("Comandos memory:")
                        print("  memory info             — Estado del subsistema")
                        print("  memory search <texto>   — Busca en la memoria")

                else:
                    # ── If there's a pending proposal, treat unknown input as response ──
                    if agent.has_pending_proposal():
                        result = await agent.process_memory_decision(raw)
                        print(result)
                    else:
                        print(f"Comando desconocido: {cmd}. Escribe 'help' para ayuda.")
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(_run_cli())