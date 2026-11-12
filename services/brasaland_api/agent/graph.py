"""
agents/support_agent/graph.py — Definición y compilación del grafo.

    START → retrieve → route_after_retrieve ─┬→ generate   → END
                                             └→ no_context → END

El grafo se compila al importar el módulo para que cualquier error
estructural aparezca al arrancar la API, no durante una request.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.support_agent import tracing
from agents.support_agent.nodes import (
    generate_node,
    no_context_node,
    retrieve_node,
    route_after_retrieve,
)
from agents.support_agent.state import SupportAgentState


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(SupportAgentState)

    graph.add_node("retrieve", tracing.traced_node("retrieve", retrieve_node))
    graph.add_node("generate", tracing.traced_node("generate", generate_node))
    graph.add_node("no_context", tracing.traced_node("no_context", no_context_node))

    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        tracing.traced_edge("route_after_retrieve", route_after_retrieve),
        {"generate": "generate", "no_context": "no_context"},
    )
    graph.add_edge("generate", END)
    graph.add_edge("no_context", END)

    return graph.compile()


support_agent_graph = build_graph()


@dataclass(frozen=True)
class AgentResult:
    run_id: str
    answer: str


def run_agent(question: str) -> AgentResult:
    """Ejecuta una corrida trazada del grafo y devuelve la respuesta y su `run_id`."""
    run_id = str(uuid4())
    tracing.start_run(run_id, question)
    try:
        final_state = support_agent_graph.invoke({"run_id": run_id, "question": question})
    except Exception as exc:
        tracing.finish_run(run_id, error=f"{type(exc).__name__}: {exc}")
        raise
    answer = final_state["answer"]
    tracing.finish_run(run_id, answer=answer)
    return AgentResult(run_id=run_id, answer=answer)
