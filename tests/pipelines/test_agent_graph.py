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

    expected_nodes = {
        "__start__", "receive_question", "router", "retrieve",
        "incident_tool", "inventory_tool",
        "generate", "no_context", "synthesizer", "__end__",
    }
    assert set(graph.nodes) == expected_nodes, (
        f"Nodos esperados: {expected_nodes}, obtenidos: {set(graph.nodes)}"
    )

    expected_edges = {
        ("__start__", "receive_question", False),
        ("receive_question", "router", True),
        ("receive_question", "__end__", True),
        ("router", "retrieve", True),
        ("router", "incident_tool", True),
        ("router", "inventory_tool", True),
        ("retrieve", "generate", True),
        ("retrieve", "no_context", True),
        ("generate", "incident_tool", True),
        ("generate", "inventory_tool", True),
        ("generate", "synthesizer", True),
        ("no_context", "incident_tool", True),
        ("no_context", "inventory_tool", True),
        ("no_context", "synthesizer", True),
        ("incident_tool", "synthesizer", False),
        ("inventory_tool", "synthesizer", False),
        ("synthesizer", "__end__", False),
    }
    actual_edges = {(edge.source, edge.target, edge.conditional) for edge in graph.edges}
    assert actual_edges == expected_edges, (
        f"Edges mismatch.\nExpected:\n{sorted(expected_edges)}\nGot:\n{sorted(actual_edges)}"
    )


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
    # La secuencia ahora incluye router, retrieve, generate, synthesizer
    names = step_names(result.run_id)
    assert "router" in names
    assert "retrieve" in names
    assert "generate" in names
    assert "synthesizer" in names
    assert names[-1] == "synthesizer"
    assert names[0] == "receive_question"
    trace = tracing.get_trace(result.run_id)
    assert trace is not None and trace["status"] == "completed"
    assert trace.get("usage_summary") == ["rag"]


def test_run_without_context_skips_llm(rag_mocks: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = []

    result = run_agent("¿Cuál es la receta secreta de la salsa Brasa?")

    assert result.answer == NO_CONTEXT_ANSWER
    mock_generate.assert_not_called()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    names = [s["name"] for s in trace["steps"]]
    assert "no_context" in names
    assert "synthesizer" in names
    assert names[-1] == "synthesizer"


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

    # La secuencia de checkpoints ahora es más larga con router y synthesizer
    next_list = [cp["next"] for cp in checkpoints]
    assert ["__start__"] in next_list
    assert ["receive_question"] in next_list
    assert ["router"] in next_list
    assert ["retrieve"] in next_list
    assert ["generate"] in next_list
    assert next_list[-1] == []  # END
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
    node_names = [step["name"] for step in trace["steps"] if step["kind"] == "node"]
    assert "receive_question" in node_names
    assert "router" in node_names
    assert "retrieve" in node_names
    assert "generate" in node_names
    assert "synthesizer" in node_names
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


# =========================================================================
# Tests de enrutamiento con tools externas (Hito 8 Part 2)
# =========================================================================


def _patch_router(monkeypatch: pytest.MonkeyPatch, intent: str) -> None:
    """Fuerza el router a devolver un intent específico sin LLM."""
    def _fake_router(*args, **kwargs):
        return intent
    import services.brasaland_api.agent.nodes as agent_nodes
    monkeypatch.setattr(agent_nodes, "_call_llm_router", _fake_router)


def test_incident_tool_route_calls_incident_then_synthesizer(
    monkeypatch: pytest.MonkeyPatch,
    rag_mocks: tuple[MagicMock, MagicMock],
) -> None:
    """Cuando el router clasifica como incident_tool, se salta retrieve y generate."""
    _patch_router(monkeypatch, "incident_tool")
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]

    with patch("services.brasaland_api.agent.nodes.run_incident_tool") as mock_run_tool:
        mock_run_tool.return_value = MagicMock(
            success=True,
            data=[{"incident_id": "INC-0001", "title": "Test", "estado": "abierta"}],
            error=None,
            elapsed_ms=12.0,
        )
        result = run_agent("¿Qué pasó con el ticket INC-0001?")

    assert result.answer is not None
    assert "INC-0001" in result.answer or "Resultados" in result.answer
    mock_retrieve.assert_not_called()
    mock_generate.assert_not_called()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    names = [s["name"] for s in trace["steps"]]
    assert "incident_tool" in names
    assert "synthesizer" in names
    assert trace.get("usage_summary") == ["incident_tool"]


def test_inventory_tool_route_calls_inventory_then_synthesizer(
    monkeypatch: pytest.MonkeyPatch,
    rag_mocks: tuple[MagicMock, MagicMock],
) -> None:
    """Cuando el router clasifica como inventory_tool, se salta retrieve y generate."""
    _patch_router(monkeypatch, "inventory_tool")
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]

    with patch("services.brasaland_api.agent.nodes.run_inventory_tool") as mock_run_tool:
        mock_run_tool.return_value = MagicMock(
            success=True,
            data=[{"name": "Pollo", "current_stock": 500.0, "unit": "kg"}],
            error=None,
            elapsed_ms=8.0,
        )
        result = run_agent("¿Cuánto pollo tenemos en inventario?")

    assert result.answer is not None
    assert "Pollo" in result.answer or "Productos" in result.answer
    mock_retrieve.assert_not_called()
    mock_generate.assert_not_called()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    names = [s["name"] for s in trace["steps"]]
    assert "inventory_tool" in names
    assert "synthesizer" in names


def test_rag_and_incident_tool_route_calls_both(
    monkeypatch: pytest.MonkeyPatch,
    rag_mocks: tuple[MagicMock, MagicMock],
) -> None:
    """Cuando el router clasifica como rag_and_incident_tool, usa ambas fuentes."""
    _patch_router(monkeypatch, "rag_and_incident_tool")
    mock_retrieve, mock_generate = rag_mocks
    mock_retrieve.return_value = [CHUNK]
    mock_generate.return_value = "Respuesta combinada."

    with patch("services.brasaland_api.agent.nodes.run_incident_tool") as mock_run_tool:
        mock_run_tool.return_value = MagicMock(
            success=True,
            data=[{"incident_id": "INC-0002", "title": "Queja alérgenos", "estado": "abierta"}],
            error=None,
            elapsed_ms=10.0,
        )
        result = run_agent("¿Hay quejas de alérgenos y qué dice la política?")

    assert result.answer is not None
    mock_retrieve.assert_called_once()
    mock_run_tool.assert_called_once()
    trace = tracing.get_trace(result.run_id)
    assert trace is not None
    names = [s["name"] for s in trace["steps"]]
    retrieve_idx = names.index("retrieve")
    incident_idx = names.index("incident_tool")
    assert retrieve_idx < incident_idx, f"retrieve ({retrieve_idx}) debe ir antes que tool ({incident_idx})"
    assert "generate" in names
    assert "synthesizer" in names


def test_keyword_router_fallback_works() -> None:
    """Verifica que el keyword router clasifica correctamente sin LLM."""
    from services.brasaland_api.agent.nodes import _keyword_router

    assert _keyword_router("¿Qué pasó con el ticket INC-0001?") == "incident_tool"
    assert _keyword_router("¿Cuánto stock de pollo tenemos?") == "inventory_tool"
    assert _keyword_router("¿Cuánto cuesta el menú infantil?") == "rag"
    assert _keyword_router("¿Hay suficiente pollo para el menú?") == "rag", (
        "La frase 'suficiente pollo' no es 'cuánto' stock, y 'menú' es RAG"
    )
    assert _keyword_router("¿Qué dice la política sobre quejas INC-0005?") == "rag_and_incident_tool"
    assert _keyword_router("Hola, ¿cómo estás?") == "rag"
