"""
agents/support_agent/state.py — Estado mínimo que viaja entre nodos.

Solo contiene lo necesario para una corrida: la pregunta, los chunks
recuperados y la respuesta. No se guarda historial de conversación.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class SupportAgentState(TypedDict):
    run_id: str
    question: str
    documents: NotRequired[list[dict[str, Any]]]
    answer: NotRequired[str]
