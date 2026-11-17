"""
services/brasaland_api/agent/graph.py — Definición, compilación y ejecución del grafo.

    START → receive_question ─┬─(pregunta vacía)→ END
                              └→ retrieve ─┬─(hay contexto)→ generate   → END
                                           └─(sin contexto)→ no_context → END

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
    no_context_node,
    receive_question_node,
    retrieve_node,
    route_after_receive,
    route_after_retrieve,
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


def define_graph() -> StateGraph:
    graph = StateGraph(SupportAgentState)

    graph.add_node("receive_question", tracing.traced_node("receive_question", receive_question_node))
    graph.add_node("retrieve", tracing.traced_node("retrieve", retrieve_node))
    graph.add_node("generate", tracing.traced_node("generate", generate_node))
    graph.add_node("no_context", tracing.traced_node("no_context", no_context_node))

    graph.add_edge(START, "receive_question")
    graph.add_conditional_edges(
        "receive_question",
        tracing.traced_edge("route_after_receive", route_after_receive),
        {"retrieve": "retrieve", "reject": END},
    )
    graph.add_conditional_edges(
        "retrieve",
        tracing.traced_edge("route_after_retrieve", route_after_retrieve),
        {"generate": "generate", "no_context": "no_context"},
    )
    graph.add_edge("generate", END)
    graph.add_edge("no_context", END)
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

    answer = final_state["answer"]
    tracing.finish_run(run_id, status="completed", answer=answer)
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
