"""
tests/pipelines/test_agent_graph.py — Grafo LangGraph del agente de soporte.

Se simulan `retrieve` y `generate_answer` de data/pipelines/rag.py para
verificar estructura, enrutamiento, trace, checkpoints y endpoints sin
Qdrant ni LLM reales.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from services.brasaland_api.agent import (
    AgentGraphBuildError,
    AgentRunError,
    build_graph,
    list_checkpoints,
    run_agent,
)
from services.brasaland_api.agent import graph as graph_module
from services.brasaland_api.agent import tracing
from services.brasaland_api.agent.nodes import EMPTY_QUESTION_ERROR, NO_CONTEXT_ANSWER

QUESTION = "¿Cuántos puntos necesito para el nivel Oro?"
CHUNK: dict[str, Any] = {
    "source_document": "loyalty-program",
    "section": "Niveles de membresía",
    "text": "Nivel Oro requiere 1.500 puntos acumulados en los últimos 12 meses.",
    "chunk_index": 3,
    "score": 0.92,
}


@pytest.fixture(autouse=True)
def isolated_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tracing, "TRACES_DB_FILE", tmp_path / "traces.json")
    monkeypatch.setattr(graph_module, "support_agent_graph", build_graph(InMemorySaver()))


@pytest.fixture
def rag_mocks() -> Iterator[tuple[MagicMock, MagicMock]]:
    with (
        patch("data.pipelines.rag.retrieve") as mock_retrieve,
        patch("data.pipelines.rag.generate_answer") as mock_generate,
        patch("data.pipelines.rag.query") as mock_query,
    ):
        yield mock_retrieve, mock_generate
        mock_query.assert_not_called()


def step_names(run_id: str) -> list[str]:
    trace = tracing.get_trace(run_id)
    assert trace is not None
    return [step["name"] for step in trace["steps"]]


def test_graph_compiles_with_conditional_edges() -> None:
    graph = build_graph().get_graph()

    assert set(graph.nodes) == {
        "__start__", "receive_question", "retrieve", "generate", "no_context", "__end__",
    }
    edges = {(edge.source, edge.target, edge.conditional) for edge in graph.edges}
    assert edges == {
        ("__start__", "receive_question", False),
        ("receive_question", "retrieve", True),
        ("receive_question", "__end__", True),
        ("retrieve", "generate", True),
        ("retrieve", "no_context", True),
        ("generate", "__end__", False),
        ("no_context", "__end__", False),
    }


def test_structural_error_fails_at_compile_time() -> None:
    broken = graph_module.define_graph()
    broken.add_edge("generate", "nodo_inexistente")

    with pytest.raises(AgentGraphBuildError, match="nodo_inexistente"):
        graph_module.compile_graph(broken)


def test_run_with_context_calls_retrieve_then_generate(
    rag_mocks: tuple[MagicMock, MagicMock],
) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Necesitas 1.500 puntos para el nivel Oro."

    result = run_agent(f"  {QUESTION}  ")

    assert result.answer == "Necesitas 1.500 puntos para el nivel Oro."
    mock_retrieve.assert_called_once_with(QUESTION)
    mock_generate.assert_called_once_with(QUESTION, [CHUNK])
    assert step_names(result.run_id) == [
        "receive_question", "route_after_receive", "retrieve", "route_after_retrieve", "generate",
    ]
    trace = tracing.get_trace(result.run_id)
    assert trace is not None and trace["status"] == "completed"
    retrieve_step = trace["steps"][2]
    assert retrieve_step["output"]["documents"] == [
        {"source_document": "loyalty-program", "section": "Niveles de membresía", "chunk_index": 3, "score": 0.92}
    ]


def test_run_without_context_skips_llm(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = []

    result = run_agent("¿Cuál es la receta secreta de la salsa Brasa?")

    assert result.answer == NO_CONTEXT_ANSWER
    mock_generate.assert_not_called()
    assert step_names(result.run_id)[-1] == "no_context"


def test_empty_question_is_rejected_before_retrieve(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, _ = rag_mocks

    result = run_agent("   ")

    assert result.answer is None
    assert result.error == EMPTY_QUESTION_ERROR
    mock_retrieve.assert_not_called()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None and trace["status"] == "rejected"
    assert step_names(result.run_id) == ["receive_question", "route_after_receive"]


def test_failed_node_raises_run_error_and_is_traced(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, _ = rag_mocks
    mock_retrieve.side_effect = RuntimeError("Qdrant no disponible")

    with pytest.raises(AgentRunError) as exc_info:
        run_agent(QUESTION)

    trace = tracing.get_trace(exc_info.value.run_id)
    assert trace is not None and trace["status"] == "error"
    failed_step = trace["steps"][-1]
    assert failed_step["name"] == "retrieve"
    assert failed_step["error"] == "RuntimeError: Qdrant no disponible"


def test_each_transition_is_checkpointed(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Respuesta."

    result = run_agent(QUESTION)
    checkpoints = list_checkpoints(result.run_id)

    assert [checkpoint["next"] for checkpoint in checkpoints] == [
        ["__start__"], ["receive_question"], ["retrieve"], ["generate"], [],
    ]
    assert "documents" in checkpoints[3]["state_keys"]
    assert "answer" in checkpoints[-1]["state_keys"]
    final_state = graph_module.support_agent_graph.get_state({"configurable": {"thread_id": result.run_id}})
    assert final_state.values["answer"] == "Respuesta."


def test_sqlite_checkpointer_persists_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rag_mocks: tuple[MagicMock, MagicMock]
) -> None:
    mock_retrieve, _ = rag_mocks
    mock_retrieve.return_value = []
    db_file = tmp_path / "checkpoints.sqlite"
    monkeypatch.setattr(
        graph_module, "support_agent_graph", build_graph(graph_module.create_sqlite_checkpointer(db_file))
    )
    run_id = run_agent(QUESTION).run_id

    monkeypatch.setattr(
        graph_module, "support_agent_graph", build_graph(graph_module.create_sqlite_checkpointer(db_file))
    )

    assert list_checkpoints(run_id)[-1]["next"] == []


def test_retrieve_node_works_with_real_rag_retrieve_defaults() -> None:
    hit = MagicMock(score=0.95, payload={k: v for k, v in CHUNK.items() if k != "score"})
    qdrant_client = MagicMock()
    qdrant_client.search.return_value = [hit]

    with (
        patch("data.pipelines.rag.embed", return_value=[0.1] * 768),
        patch("data.pipelines.rag._get_qdrant_client", return_value=qdrant_client),
        patch("data.pipelines.rag.generate_answer", return_value="Respuesta."),
    ):
        result = run_agent(QUESTION)

    assert result.answer == "Respuesta."


@pytest.fixture
def client() -> TestClient:
    from services.brasaland_api.main import app

    return TestClient(app, raise_server_exceptions=False)


def test_agent_query_endpoint_returns_answer_trace_and_checkpoints(
    client: TestClient, rag_mocks: tuple[MagicMock, MagicMock]
) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Necesitas 1.500 puntos."

    response = client.post("/agent/query", json={"question": QUESTION})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Necesitas 1.500 puntos."
    trace = client.get(f"/agent/traces/{body['run_id']}").json()
    assert [step["name"] for step in trace["steps"] if step["kind"] == "node"] == [
        "receive_question", "retrieve", "generate",
    ]
    checkpoints = client.get(f"/agent/traces/{body['run_id']}/checkpoints")
    assert checkpoints.status_code == 200
    assert checkpoints.json()[-1]["next"] == []


def test_agent_query_endpoint_rejects_empty_question(
    client: TestClient, rag_mocks: tuple[MagicMock, MagicMock]
) -> None:
    response = client.post("/agent/query", json={"question": "  "})

    assert response.status_code == 400
    assert response.json()["detail"] == EMPTY_QUESTION_ERROR
    assert response.json()["run_id"]


def test_agent_query_endpoint_hides_internal_errors(
    client: TestClient, rag_mocks: tuple[MagicMock, MagicMock]
) -> None:
    mock_retrieve, _ = rag_mocks
    mock_retrieve.side_effect = RuntimeError("credencial secreta de Qdrant")

    response = client.post("/agent/query", json={"question": QUESTION})

    assert response.status_code == 503
    body = response.json()
    assert "secreta" not in response.text
    assert "Traceback" not in response.text
    assert body["detail"].startswith("El agente no pudo procesar la pregunta")
    assert client.get(f"/agent/traces/{body['run_id']}").json()["status"] == "error"


def test_unknown_run_returns_404(client: TestClient) -> None:
    assert client.get("/agent/traces/no-existe").status_code == 404
    assert client.get("/agent/traces/no-existe/checkpoints").status_code == 404
