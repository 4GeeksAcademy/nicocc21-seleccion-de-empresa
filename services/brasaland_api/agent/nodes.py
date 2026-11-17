"""
services/brasaland_api/agent/nodes.py — Nodos y condiciones de salida del grafo.

Cada nodo tiene una sola responsabilidad. La lógica RAG no se reescribe: los
nodos llaman por separado a `retrieve` y `generate_answer` de
data/pipelines/rag.py. Nunca se usa `query()`, que haría ambas cosas a la vez.

Integración de memoria (Hito 8):
  - memory_evaluate: tras generar la respuesta, evalúa si la interacción
    contiene algo memorable y, de ser así, inyecta la propuesta en el estado.
"""

from __future__ import annotations

from typing import Any, Literal

from data.pipelines import rag

from services.brasaland_api.agent.memory import MemoryManager
from services.brasaland_api.agent.state import SupportAgentState

EMPTY_QUESTION_ERROR = "La pregunta no puede estar vacía."
NO_CONTEXT_ANSWER = (
    "No tengo información suficiente en la base de conocimiento "
    "para responder esa pregunta."
)

# Instancia compartida del gestor de memoria (singleton a nivel de módulo)
_memory_manager: MemoryManager | None = None


def _get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# ── Nodos RAG ──────────────────────────────────────────────────────────


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


# ── Nodos de Memoria (Hito 8) ──────────────────────────────────────────


def memory_context_node(state: SupportAgentState) -> dict[str, Any]:
    """Inyecta contexto de memoria relevante antes de generar la respuesta.

    Recupera memorias almacenadas para el local (si se conoce) y las
    adjunta al estado para que `generate` pueda usarlas.
    """
    location_id = _infer_location(state.get("question", ""))
    if not location_id:
        return {}

    try:
        mm = _get_memory_manager()
        context = mm.get_context(location_id)
        if context:
            return {"memory_context": context}
    except Exception:
        pass

    return {}


def memory_evaluate_node(state: SupportAgentState) -> dict[str, Any]:
    """Evalúa la interacción completa para detectar hechos memorables.

    Se ejecuta DESPUÉS de generate. Si detecta algo memorable,
    inyecta `memory_proposal` y `memory_prompt` en el estado para
    que el cliente pueda mostrar la confirmación al usuario.
    """
    location_id = _infer_location(state.get("question", ""))
    if not location_id:
        return {}

    # Combinar pregunta + respuesta como interacción a evaluar
    interaction = f"{state.get('question', '')}\n{state.get('answer', '')}"

    try:
        mm = _get_memory_manager()
        proposal, prompt = mm.evaluate_and_propose(
            interaction_text=interaction,
            location_id=location_id,
        )
        if proposal and prompt:
            return {
                "memory_proposal": proposal.id,
                "memory_prompt": prompt,
            }
    except Exception:
        pass

    return {}


# ── Rutas ──────────────────────────────────────────────────────────────


def route_after_receive(state: SupportAgentState) -> Literal["retrieve", "reject"]:
    return "reject" if state.get("error") else "retrieve"


def route_after_retrieve(state: SupportAgentState) -> Literal["generate", "no_context"]:
    return "generate" if state.get("documents") else "no_context"


# ── Helpers ────────────────────────────────────────────────────────────

# Expresión regular para detectar IDs de local tipo L01, L02, ..., L14
_LOCATION_PATTERN = __import__("re").compile(r"\b(L\d{2})\b", __import__("re").IGNORECASE)


def _infer_location(text: str) -> str:
    """Intenta extraer un ID de local del texto de la pregunta."""
    if not text:
        return ""
    match = _LOCATION_PATTERN.search(text)
    return match.group(1).upper() if match else ""
