"""
agents/support_agent/nodes.py — Nodos del grafo, una responsabilidad cada uno.

La lógica RAG no se reescribe: los nodos delegan en `retrieve` y
`generate_answer` de data/pipelines/rag.py.
"""

from __future__ import annotations

from typing import Any, Literal

from data.pipelines import rag

from agents.support_agent.state import SupportAgentState

NO_CONTEXT_ANSWER = (
    "No tengo información suficiente en la base de conocimiento "
    "para responder esa pregunta."
)


def retrieve_node(state: SupportAgentState) -> dict[str, Any]:
    """Recupera los chunks relevantes para la pregunta."""
    return {"documents": rag.retrieve(state["question"])}


def generate_node(state: SupportAgentState) -> dict[str, Any]:
    """Genera la respuesta con el LLM usando solo el contexto recuperado."""
    return {"answer": rag.generate_answer(state["question"], state.get("documents", []))}


def no_context_node(state: SupportAgentState) -> dict[str, Any]:
    """Responde honestamente cuando no hay contexto, sin llamar al LLM."""
    return {"answer": NO_CONTEXT_ANSWER}


def route_after_retrieve(state: SupportAgentState) -> Literal["generate", "no_context"]:
    """Decide si hay contexto suficiente para generar una respuesta."""
    return "generate" if state.get("documents") else "no_context"
