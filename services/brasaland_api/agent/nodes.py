"""
services/brasaland_api/agent/nodes.py — Nodos y condiciones de salida del grafo.

Cada nodo tiene una sola responsabilidad. La lógica RAG no se reescribe: los
nodos llaman por separado a `retrieve` y `generate_answer` de
data/pipelines/rag.py. Nunca se usa `query()`, que haría ambas cosas a la vez.
"""

from __future__ import annotations

from typing import Any, Literal

from data.pipelines import rag

from services.brasaland_api.agent.state import SupportAgentState

EMPTY_QUESTION_ERROR = "La pregunta no puede estar vacía."
NO_CONTEXT_ANSWER = (
    "No tengo información suficiente en la base de conocimiento "
    "para responder esa pregunta."
)


def receive_question_node(state: SupportAgentState) -> dict[str, Any]:
    """Normaliza la pregunta y la valida antes de recuperar contexto."""
    question = state["question"].strip()
    if not question:
        return {"question": question, "error": EMPTY_QUESTION_ERROR}
    return {"question": question}


def retrieve_node(state: SupportAgentState) -> dict[str, Any]:
    """Recupera los chunks que superan el umbral de similitud."""
    return {"documents": rag.retrieve(state["question"])}


def generate_node(state: SupportAgentState) -> dict[str, Any]:
    """Genera la respuesta usando solo el contexto que ya recuperó `retrieve`."""
    return {"answer": rag.generate_answer(state["question"], state.get("documents", []))}


def no_context_node(state: SupportAgentState) -> dict[str, Any]:
    """Responde con honestidad cuando no hay contexto, sin llamar al LLM."""
    return {"answer": NO_CONTEXT_ANSWER}


def route_after_receive(state: SupportAgentState) -> Literal["retrieve", "reject"]:
    return "reject" if state.get("error") else "retrieve"


def route_after_retrieve(state: SupportAgentState) -> Literal["generate", "no_context"]:
    return "generate" if state.get("documents") else "no_context"
