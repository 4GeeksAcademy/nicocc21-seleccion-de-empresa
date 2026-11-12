"""
services/brasaland_api/agent/graph.py — Definición, compilación y ejecución del grafo.

Topología Hito 8 Part 2 (con tools externas):

    START → receive_question ─┬─(vacía)→ END
                              └→ router ─┬─ rag_only              → retrieve ─→ synthesizer ─→ END
                                          ├─ incident_tool_only    → incident_tool → synthesizer ─→ END
                                          ├─ inventory_tool_only   → inventory_tool → synthesizer ─→ END
                                          ├─ rag_and_incident      → retrieve → incident_tool → synthesizer ─→ END
                                          └─ rag_and_inventory     → retrieve → inventory_tool → synthesizer ─→ END

El grafo se compila al importar el módulo para que cualquier error estructural
aparezca al arrancar la API, no durante una request. Cada transición queda
guardada por el checkpointer usando `run_id` como `thread_id`.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from services.brasaland_api.agent import tracing
from services.brasaland_api.agent.nodes import (
    generate_node,
    incident_tool_node,
    inventory_tool_node,
    no_context_node,
    receive_question_node,
    retrieve_node,
    router_node,
    route_after_receive,
    route_after_retrieve,
    route_after_router,
    route_tool_fallback,
    synthesizer_node,
)
from services.brasaland_api.agent.state import SupportAgentState

CHECKPOINTS_DB_FILE = Path(
    os.getenv("AGENT_CHECKPOINTS_DB", str(tracing.AGENT_DATA_DIR / "checkpoints.sqlite"))
)


class AgentGraphBuildError(RuntimeError):
    """El grafo tiene un error estructural y no se puede compilar."""


class AgentRunError(RuntimeError):
    """Un nodo falló durante la corrida; el detalle queda en el trace."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"La corrida {run_id} falló")
        self.run_id = run_id


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    answer: str | None
    error: str | None = None


def _load_env() -> None:
    """Carga variables de entorno desde env/backend.example si no están ya."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_path = Path(__file__).resolve().parents[3] / "env" / "backend.example"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def define_graph() -> StateGraph:
    graph = StateGraph(SupportAgentState)

    # Nodos base
    graph.add_node("receive_question", tracing.traced_node("receive_question", receive_question_node))
    graph.add_node("router", tracing.traced_node("router", router_node))
    graph.add_node("retrieve", tracing.traced_node("retrieve", retrieve_node))
    graph.add_node("generate", tracing.traced_node("generate", generate_node))
    graph.add_node("no_context", tracing.traced_node("no_context", no_context_node))

    # Nodos de tools externas
    graph.add_node("incident_tool", tracing.traced_node("incident_tool", incident_tool_node))
    graph.add_node("inventory_tool", tracing.traced_node("inventory_tool", inventory_tool_node))

    # Nodo sintetizador final
    graph.add_node("synthesizer", tracing.traced_node("synthesizer", synthesizer_node))

    # === Aristas ===
    graph.add_edge(START, "receive_question")

    # receive_question → router (o END si vacía)
    graph.add_conditional_edges(
        "receive_question",
        tracing.traced_edge("route_after_receive", route_after_receive),
        {"router": "router", "reject": END},
    )

    # router → 5 posibles caminos
    graph.add_conditional_edges(
        "router",
        tracing.traced_edge("route_after_router", route_after_router),
        {
            "rag_only": "retrieve",
            "incident_tool_only": "incident_tool",
            "inventory_tool_only": "inventory_tool",
            "rag_and_incident": "retrieve",
            "rag_and_inventory": "retrieve",
        },
    )

    # retrieve → ruta combinada (contexto + tool según intent)
    # Flujos:
    #   intent=rag_only:    retrieve → (generate|no_context) → synthesizer
    #   intent=rag_and_*:   retrieve → (generate|no_context) → (tool) → synthesizer
    #   intent=tool_only:   (no pasa por retrieve en ese caso)
    def _route_after_retrieve_combined(state: SupportAgentState) -> str:
        """Enruta según contexto RAG e intent.

        Si hay contexto, primero va a generate (o no_context si no hay).
        Si además hay intención combinada, después de generate irá a la tool.
        Elegimos el destino inmediato:
        - Sin documentos → no_context
        - Con documentos y solo RAG → generate (y luego generate→synthesizer)
        - Con documentos y RAG+tool → generate (y luego generate→tool)
        - Sin documentos y RAG+tool → no_context (y luego no_context→tool)
        """
        has_docs = bool(state.get("documents"))
        intent = state.get("intent", "rag")

        if intent in ("rag_and_incident_tool", "rag_and_inventory_tool"):
            # En modo combinado, siempre va a generate/no_context primero,
            # luego la arista generate→synthesizer se reemplaza por generate→tool
            return "generate" if has_docs else "no_context"
        # RAG solo
        return "generate" if has_docs else "no_context"

    graph.add_conditional_edges(
        "retrieve",
        tracing.traced_edge("route_after_retrieve_combined", _route_after_retrieve_combined),
        {"generate": "generate", "no_context": "no_context"},
    )

    # generate y no_context → synthesizer O tool según intent
    def _route_after_llm(state: SupportAgentState) -> str:
        """Después de generate o no_context, va a la tool si es combinado, si no a synthesizer."""
        intent = state.get("intent", "rag")
        if intent == "rag_and_incident_tool":
            return "incident_tool"
        elif intent == "rag_and_inventory_tool":
            return "inventory_tool"
        return "synthesizer"

    graph.add_conditional_edges(
        "generate",
        tracing.traced_edge("route_after_llm", _route_after_llm),
        {"incident_tool": "incident_tool", "inventory_tool": "inventory_tool", "synthesizer": "synthesizer"},
    )
    graph.add_conditional_edges(
        "no_context",
        tracing.traced_edge("route_after_llm", _route_after_llm),
        {"incident_tool": "incident_tool", "inventory_tool": "inventory_tool", "synthesizer": "synthesizer"},
    )

    # Después de cada tool → synthesizer
    graph.add_edge("incident_tool", "synthesizer")
    graph.add_edge("inventory_tool", "synthesizer")

    # synthesizer → END
    graph.add_edge("synthesizer", END)

    return graph


def compile_graph(
    graph: StateGraph, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph:
    try:
        return graph.compile(checkpointer=checkpointer)
    except Exception as exc:
        raise AgentGraphBuildError(f"El grafo del agente no es válido: {exc}") from exc


def create_sqlite_checkpointer(db_file: Path = CHECKPOINTS_DB_FILE) -> SqliteSaver:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(db_file, check_same_thread=False))


def build_graph(checkpointer: BaseCheckpointSaver[Any] | None = None) -> CompiledStateGraph:
    return compile_graph(define_graph(), checkpointer)


support_agent_graph = build_graph(create_sqlite_checkpointer())


def _config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def run_agent(question: str) -> AgentResult:
    """Ejecuta una corrida trazada y con checkpoints del grafo."""
    run_id = str(uuid4())
    tracing.start_run(run_id, question)
    try:
        final_state = support_agent_graph.invoke(
            {"run_id": run_id, "question": question}, _config(run_id)
        )
    except Exception as exc:
        tracing.finish_run(run_id, status="error", error=f"{type(exc).__name__}: {exc}")
        raise AgentRunError(run_id) from exc

    if error := final_state.get("error"):
        tracing.finish_run(run_id, status="rejected", error=error)
        return AgentResult(run_id=run_id, answer=None, error=error)

    answer = final_state.get("answer") or final_state.get("error", "Sin respuesta disponible")
    usage_summary = final_state.get("usage_summary")
    tracing.finish_run(run_id, status="completed", answer=answer, usage_summary=usage_summary)
    return AgentResult(run_id=run_id, answer=answer)


def list_checkpoints(run_id: str) -> list[dict[str, Any]]:
    """Devuelve las transiciones guardadas de una corrida, en orden cronológico."""
    history = list(support_agent_graph.get_state_history(_config(run_id)))
    return [
        {
            "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
            "step": snapshot.metadata.get("step") if snapshot.metadata else None,
            "source": snapshot.metadata.get("source") if snapshot.metadata else None,
            "next": list(snapshot.next),
            "state_keys": sorted(snapshot.values),
            "created_at": snapshot.created_at,
        }
        for snapshot in reversed(history)
    ]
