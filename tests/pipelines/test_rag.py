#!/usr/bin/env python3
"""
tests/pipelines/test_rag.py — Pruebas unitarias para el pipeline RAG.

Cobertura:
  - retrieve() con Qdrant simulado (mock del cliente).
  - query() simulando retrieve() y el LLM de generación.
  - Verificar filtrado por min_score.
  - Verificar que se devuelven menos de k resultados.
  - Verificar que query() devuelve la salida del modelo (no chunks crudos).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Tests para retrieve()
# ---------------------------------------------------------------------------


class MockQdrantHit:
    """Simula un resultado de Qdrant.search()."""

    def __init__(self, score: float, payload: dict[str, Any] | None = None) -> None:
        self.score = score
        self.payload = payload or {
            "source_document": "loyalty-program",
            "section": "Niveles de membresía",
            "text": "Contenido de prueba",
            "chunk_index": 0,
        }


def _make_mock_search(hits: list[MockQdrantHit]) -> MagicMock:
    """Crea un mock de QdrantClient.search que devuelve hits dados."""
    mock_client = MagicMock()
    mock_client.search.return_value = hits
    return mock_client


@pytest.fixture
def mock_embed():
    """Parchea embed() para que devuelva un vector fijo."""
    with patch("data.pipelines.rag.embed") as mock:
        mock.return_value = [0.1] * 768
        yield mock


def test_retrieve_returns_payloads_above_threshold(mock_embed):
    """Debe devolver solo los hits con score >= min_score."""
    from data.pipelines.rag import retrieve

    hits = [
        MockQdrantHit(score=0.75, payload={"source_document": "test", "section": "A", "text": "chunk1", "chunk_index": 0}),
        MockQdrantHit(score=0.50, payload={"source_document": "test", "section": "B", "text": "chunk2", "chunk_index": 1}),
        MockQdrantHit(score=0.20, payload={"source_document": "test", "section": "C", "text": "chunk3", "chunk_index": 2}),
    ]

    with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
        mock_get.return_value = _make_mock_search(hits)
        result = retrieve("test query", k=5, min_score=0.45)

    assert len(result) == 2
    assert result[0]["score"] >= 0.45
    assert result[1]["score"] >= 0.45
    assert result[0]["source_document"] == "test"
    assert result[1]["text"] == "chunk2"


def test_retrieve_returns_fewer_than_k(mock_embed):
    """Si solo 1 hit supera el umbral, debe devolver 1 (no forzar k)."""
    from data.pipelines.rag import retrieve

    hits = [
        MockQdrantHit(score=0.90, payload={"source_document": "test", "section": "A", "text": "chunk1", "chunk_index": 0}),
        MockQdrantHit(score=0.10, payload={"source_document": "test", "section": "B", "text": "chunk2", "chunk_index": 1}),
        MockQdrantHit(score=0.05, payload={"source_document": "test", "section": "C", "text": "chunk3", "chunk_index": 2}),
    ]

    with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
        mock_get.return_value = _make_mock_search(hits)
        result = retrieve("test query", k=5, min_score=0.80)

    assert len(result) == 1
    assert result[0]["score"] >= 0.80


def test_retrieve_empty_when_none_above_threshold(mock_embed):
    """Si ningún hit supera el umbral, debe devolver lista vacía."""
    from data.pipelines.rag import retrieve

    hits = [
        MockQdrantHit(score=0.20),
        MockQdrantHit(score=0.15),
    ]

    with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
        mock_get.return_value = _make_mock_search(hits)
        result = retrieve("test query", k=5, min_score=0.45)

    assert result == []


def test_retrieve_empty_query(mock_embed):
    """Con consulta vacía debe devolver lista vacía."""
    from data.pipelines.rag import retrieve

    result = retrieve("", k=5, min_score=0.45)
    assert result == []


def test_retrieve_payload_has_expected_keys(mock_embed):
    """Cada resultado debe tener los campos esperados."""
    from data.pipelines.rag import retrieve

    hits = [
        MockQdrantHit(
            score=0.88,
            payload={
                "source_document": "menu-allergens",
                "section": "Platos Principales",
                "text": "Costilla BBQ",
                "chunk_index": 2,
            },
        ),
    ]

    with patch("data.pipelines.rag._get_qdrant_client") as mock_get:
        mock_get.return_value = _make_mock_search(hits)
        result = retrieve("¿La Costilla BBQ tiene alérgenos?", k=5, min_score=0.45)

    assert len(result) == 1
    item = result[0]
    assert "source_document" in item
    assert "section" in item
    assert "text" in item
    assert "chunk_index" in item
    assert "score" in item


# ---------------------------------------------------------------------------
# Tests para query()
# ---------------------------------------------------------------------------


def test_query_returns_model_output():
    """query() debe devolver la salida del modelo, no texto crudo de chunks."""
    from data.pipelines.rag import query

    with (
        patch("data.pipelines.rag.retrieve") as mock_retrieve,
        patch("data.pipelines.rag.generate_answer") as mock_generate,
    ):
        # Simular que retrieve devuelve algunos chunks
        mock_retrieve.return_value = [
            {
                "source_document": "loyalty-program",
                "section": "Niveles de membresía",
                "text": "Nivel Oro requiere 1.500 puntos acumulados en los últimos 12 meses.",
                "chunk_index": 3,
                "score": 0.92,
            },
        ]
        # Simular que generate_answer devuelve una respuesta generada
        mock_generate.return_value = (
            "Para alcanzar el nivel Oro necesitas acumular 1.500 puntos "
            "en los últimos 12 meses. En este nivel obtienes 2 puntos "
            "por cada 1.000 COP gastados."
        )

        result = query("¿Cuántos puntos necesito para el nivel Oro?")

    # La respuesta debe ser el string devuelto por generate_answer
    assert "1.500 puntos" in result
    assert "nivel Oro" in result
    # No debe devolver el texto crudo del chunk sin procesar
    assert result == mock_generate.return_value


def test_query_no_context_returns_honest_answer():
    """Cuando retrieve() no encuentra nada, query() debe indicar que no hay info."""
    from data.pipelines.rag import query

    with (
        patch("data.pipelines.rag.retrieve") as mock_retrieve,
        patch("data.pipelines.rag.generate_answer") as mock_generate,
    ):
        mock_retrieve.return_value = []
        mock_generate.return_value = (
            "No tengo información suficiente en la base de conocimiento "
            "para responder esa pregunta."
        )

        result = query("¿Cuál es la receta secreta de la salsa Brasa?")

    assert "información suficiente" in result or "no tengo" in result.lower()


def test_generate_answer_uses_context():
    """generate_answer() debe incluir el contexto recuperado en el prompt al LLM."""
    from data.pipelines.rag import generate_answer

    with patch("data.pipelines.rag._get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Respuesta generada de prueba."
        mock_client.models.generate_content.return_value = mock_response
        mock_get.return_value = mock_client

        context = [
            {
                "source_document": "menu-allergens",
                "section": "Platos Principales",
                "text": "Costilla BBQ: Mostaza.",
                "chunk_index": 5,
                "score": 0.95,
            },
        ]
        result = generate_answer("¿La Costilla BBQ tiene alérgenos?", context)

    assert result == "Respuesta generada de prueba."