"""
tests/pipelines/test_agent_evals.py — Evals del agente de soporte sobre traces grabados.

Los evals NO ejecutan el grafo en vivo: leen los traces exportados por
`uv run python -m services.brasaland_api.agent.record_traces` en
tests/pipelines/fixtures/agent_traces/ y verifican el recorrido del grafo y el
anclaje de la respuesta en docs/company-knowledge-base/.

Ejecución:
    uv run pytest tests/pipelines/test_agent_evals.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from services.brasaland_api.agent.nodes import EMPTY_QUESTION_ERROR, NO_CONTEXT_ANSWER
from services.brasaland_api.agent.record_traces import EVAL_QUESTIONS, FIXTURES_DIR, REPO_ROOT

KNOWLEDGE_BASE_DIR = REPO_ROOT / "docs" / "company-knowledge-base"


def load_trace(case_id: str) -> dict[str, Any]:
    trace_file = FIXTURES_DIR / f"{case_id}.json"
    if not trace_file.exists():
        pytest.skip(
            f"Falta el trace grabado '{trace_file.name}'. "
            "Ejecuta: uv run python -m services.brasaland_api.agent.record_traces"
        )
    trace: dict[str, Any] = json.loads(trace_file.read_text(encoding="utf-8"))
    assert trace["question"] == EVAL_QUESTIONS[case_id], "El trace no corresponde a la pregunta del eval"
    return trace


def executed_nodes(trace: dict[str, Any]) -> list[str]:
    return [step["name"] for step in trace["steps"] if step["kind"] == "node"]


def retrieved_sources(trace: dict[str, Any]) -> list[str]:
    retrieve_step = next(step for step in trace["steps"] if step["name"] == "retrieve")
    return [doc["source_document"] for doc in retrieve_step["output"]["documents"]]


def knowledge_base_text(file_name: str) -> str:
    return (KNOWLEDGE_BASE_DIR / file_name).read_text(encoding="utf-8")


def test_eval_retrieve_runs_before_generate() -> None:
    trace = load_trace("loyalty_gold_tier")

    assert trace["status"] == "completed"
    nodes = executed_nodes(trace)
    assert "retrieve" in nodes
    assert "generate" in nodes
    # El orden debe ser: receive_question → router → retrieve → generate → synthesizer
    retrieve_idx = nodes.index("retrieve")
    generate_idx = nodes.index("generate")
    assert retrieve_idx < generate_idx, f"retrieve ({retrieve_idx}) debe ir antes que generate ({generate_idx})"


def test_eval_gold_tier_answer_is_grounded_in_loyalty_policy() -> None:
    assert "Nivel Oro (1.500+ puntos" in knowledge_base_text("brasaland-loyalty-program.es.md")
    trace = load_trace("loyalty_gold_tier")

    assert any("loyalty" in source for source in retrieved_sources(trace)), (
        f"Ninguna fuente contiene 'loyalty' en {retrieved_sources(trace)}"
    )
    assert re.search(r"1[.,\s]?500", trace["answer"]), trace["answer"]
    # La pregunta usó RAG, no tool
    assert trace.get("usage_summary") is None or "rag" in (trace.get("usage_summary") or [])


def test_eval_ceviche_allergens_are_grounded_in_menu_guide() -> None:
    assert "| Ceviche Brasaland | Pescado |" in knowledge_base_text("brasaland-menu-allergens.es.md")
    trace = load_trace("ceviche_allergens")

    assert trace["status"] == "completed"
    assert any("allergen" in source for source in retrieved_sources(trace))
    assert "pescado" in trace["answer"].lower(), trace["answer"]


def test_eval_out_of_scope_question_routes_to_no_context() -> None:
    trace = load_trace("out_of_scope")

    route = next(step for step in trace["steps"] if step["name"] == "route_after_retrieve")
    assert route["output"] == "no_context"
    assert "generate" not in executed_nodes(trace)
    assert trace["answer"] == NO_CONTEXT_ANSWER


def test_eval_empty_question_is_rejected_before_retrieve() -> None:
    trace = load_trace("empty_question")

    assert trace["status"] == "rejected"
    assert trace["error"] == EMPTY_QUESTION_ERROR
    assert executed_nodes(trace) == ["receive_question"]


# =========================================================================
#  Evals de enrutamiento con tools externas (Hito 8 Part 2)
# =========================================================================


EVAL_ROUTING_QUESTIONS: dict[str, str] = {
    "incident_tool_query": "¿Qué pasó con el ticket INC-0003?",
    "rag_query": "¿Cuánto cuesta el menú infantil?",
    "fallback_empty": "   ",
}


def test_eval_incident_question_routes_to_tool_not_rag() -> None:
    """Una pregunta sobre un ticket concreto debe usar la tool de incidentes, no RAG."""
    trace = load_trace("incident_tool_query")
    nodes = executed_nodes(trace)

    assert "incident_tool" in nodes, (
        f"La pregunta de incidente debería usar incident_tool. Nodos: {nodes}"
    )
    assert "retrieve" not in nodes or "generate" not in nodes, (
        "No debería llamar RAG para una pregunta que solo necesita tool"
    )
    assert trace.get("usage_summary") is None or "incident_tool" in (trace.get("usage_summary") or [])


def test_eval_rag_query_routes_to_rag_not_tool() -> None:
    """Una pregunta sobre políticas debe usar RAG, no las tools."""
    trace = load_trace("rag_query")
    nodes = executed_nodes(trace)

    assert "retrieve" in nodes, f"Debería usar retrieve. Nodos: {nodes}"
    assert "generate" in nodes, f"Debería usar generate. Nodos: {nodes}"
    assert "incident_tool" not in nodes, "No debería llamar tool de incidentes para pregunta RAG"
    assert "inventory_tool" not in nodes, "No debería llamar tool de inventario para pregunta RAG"
    assert trace.get("usage_summary") is None or "rag" in (trace.get("usage_summary") or [])


def test_eval_fallback_empty_question() -> None:
    """Una pregunta vacía debe rechazarse antes de cualquier nodo."""
    trace = load_trace("fallback_empty")
    assert trace["status"] == "rejected"
    assert trace["error"] == EMPTY_QUESTION_ERROR
    nodes = executed_nodes(trace)
    assert len(nodes) <= 1, f"Solo debería llegar a receive_question. Nodos: {nodes}"
