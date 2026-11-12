"""
services/brasaland_api/agent/state.py — Estado del agente de soporte.

Incluye:
  - run_id / question / answer / error (base)
  - documents (recuperados por el RAG)
  - intent (cómo el router clasificó la pregunta)
  - tool_input / tool_result (para herramientas externas)
  - usage (qué se usó: rag, tool, o ambos)
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class SupportAgentState(TypedDict):
    # --- Base ---
    run_id: str
    question: str
    answer: NotRequired[str]
    error: NotRequired[str]

    # --- RAG ---
    documents: NotRequired[list[dict[str, Any]]]

    # --- Routing ---
    intent: NotRequired[Literal["rag", "incident_tool", "inventory_tool", "rag_and_incident_tool", "rag_and_inventory_tool"]]

    # --- Tools ---
    tool_input: NotRequired[dict[str, Any]]
    tool_result: NotRequired[dict[str, Any]]

    # --- Usage metadata ---
    usage_summary: NotRequired[list[str]]
