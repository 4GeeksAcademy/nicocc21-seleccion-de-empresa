"""
tests/agents/test_support_agent_graph.py — Grafo LangGraph del agente de soporte.

Se simulan `retrieve` y `generate_answer` de data/pipelines/rag.py para
verificar estructura, enrutamiento y trace sin Qdrant ni LLM reales.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.support_agent import build_graph, run_agent, tracing
from agents.support_agent.nodes import NO_CONTEXT_ANSWER

CHUNK: dict[str, Any] = {
    "source_document": "loyalty-program",
    "section": "Niveles de membresía",
    "text": "Nivel Oro requiere 1.500 puntos acumulados en los últimos 12 meses.",
    "chunk_index": 3,
    "score": 0.92,
}


@pytest.fixture(autouse=True)
def traces_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_file = tmp_path / "traces.json"
    monkeypatch.setattr(tracing, "TRACES_DB_FILE", db_file)
    return db_file


@pytest.fixture
def rag_mocks() -> Iterator[tuple[MagicMock, MagicMock]]:
    with (
        patch("data.pipelines.rag.retrieve") as mock_retrieve,
        patch("data.pipelines.rag.generate_answer") as mock_generate,
    ):
        yield mock_retrieve, mock_generate


def test_graph_compiles_with_expected_structure() -> None:
    graph = build_graph().get_graph()

    assert set(graph.nodes) == {"__start__", "retrieve", "generate", "no_context", "__end__"}
    edges = {(edge.source, edge.target, edge.conditional) for edge in graph.edges}
    assert edges == {
        ("__start__", "retrieve", False),
        ("retrieve", "generate", True),
        ("retrieve", "no_context", True),
        ("generate", "__end__", False),
        ("no_context", "__end__", False),
    }


def test_run_with_context_generates_answer_and_traces_each_step(
    rag_mocks: tuple[MagicMock, MagicMock],
) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Necesitas 1.500 puntos para el nivel Oro."

    result = run_agent("¿Cuántos puntos necesito para el nivel Oro?")

    assert result.answer == "Necesitas 1.500 puntos para el nivel Oro."
    mock_retrieve.assert_called_once_with("¿Cuántos puntos necesito para el nivel Oro?")
    mock_generate.assert_called_once_with("¿Cuántos puntos necesito para el nivel Oro?", [CHUNK])

    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    assert trace["status"] == "completed"
    assert trace["answer"] == result.answer
    assert [step["name"] for step in trace["steps"]] == [
        "retrieve",
        "route_after_retrieve",
        "generate",
    ]
    retrieve_step, route_step, _ = trace["steps"]
    assert retrieve_step["output"]["documents"] == [
        {"source_document": "loyalty-program", "section": "Niveles de membresía", "chunk_index": 3, "score": 0.92}
    ]
    assert route_step["kind"] == "edge"
    assert route_step["output"] == "generate"


def test_run_without_context_skips_llm(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = []

    result = run_agent("¿Cuál es la receta secreta de la salsa Brasa?")

    assert result.answer == NO_CONTEXT_ANSWER
    mock_generate.assert_not_called()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    assert [step["name"] for step in trace["steps"]] == [
        "retrieve",
        "route_after_retrieve",
        "no_context",
    ]


def test_failed_node_is_recorded_in_trace(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, _ = rag_mocks
    mock_retrieve.side_effect = RuntimeError("Qdrant no disponible")

    with patch("agents.support_agent.graph.uuid4", return_value="run-fallida"):
        with pytest.raises(RuntimeError):
            run_agent("¿Horario del local?")

    trace = tracing.get_trace("run-fallida")
    assert trace is not None
    assert trace["status"] == "error"
    assert trace["steps"][0]["error"] == "RuntimeError: Qdrant no disponible"


def test_retrieve_node_works_with_real_rag_retrieve_defaults() -> None:
    """El nodo llama al `retrieve` real con sus parámetros por defecto."""
    hit = MagicMock(score=0.95, payload={**{k: v for k, v in CHUNK.items() if k != "score"}})
    client = MagicMock()
    client.search.return_value = [hit]

    with (
        patch("data.pipelines.rag.embed", return_value=[0.1] * 768),
        patch("data.pipelines.rag._get_qdrant_client", return_value=client),
        patch("data.pipelines.rag.generate_answer", return_value="Respuesta."),
    ):
        result = run_agent("¿Cuántos puntos necesito para el nivel Oro?")

    assert result.answer == "Respuesta."


def test_api_returns_run_id_and_exposes_trace(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    from services.brasaland_api.main import app

    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Necesitas 1.500 puntos."
    client = TestClient(app)

    response = client.post("/knowledge/query", json={"question": "¿Nivel Oro?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Necesitas 1.500 puntos."
    trace_response = client.get(f"/agent/traces/{body['run_id']}")
    assert trace_response.status_code == 200
    assert [step["name"] for step in trace_response.json()["steps"]] == [
        "retrieve",
        "route_after_retrieve",
        "generate",
    ]
    assert client.get("/agent/traces/no-existe").status_code == 404
