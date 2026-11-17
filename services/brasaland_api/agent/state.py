"""
services/brasaland_api/agent/state.py — Estado mínimo que viaja entre nodos.

Solo contiene lo que un nodo necesita para decidir el siguiente paso: la
pregunta, los chunks recuperados, la respuesta y un error de validación.
No se guarda historial de conversación: cada corrida es una pregunta aislada.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class SupportAgentState(TypedDict):
    run_id: str
    question: str
    documents: NotRequired[list[dict[str, Any]]]
    answer: NotRequired[str]
    error: NotRequired[str]
