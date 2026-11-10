#!/usr/bin/env python3
"""
data/pipelines/rag.py — Pipeline RAG de recuperación y generación.

Responsabilidades:
  1. retrieve(query, *, k, min_score) : embebe la consulta, busca en Qdrant
     los k vecinos más cercanos, filtra por min_score y devuelve payloads.
  2. generate_answer(question, context) : arma el prompt con el contexto
     recuperado y llama al LLM de generación.
  3. query(question)                 : orquesta retrieve + generate_answer.
     Es la ÚNICA función que deben llamar consumidores externos.

Dos modelos separados:
  - Embeddings: text-embedding-004 (Google, 768-d, vía embed() en data/process/rag.py)
  - Generación: gemini-2.0-flash   (Google, vía generate_answer())

Configuración vía variables de entorno (ver env/rag.example).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from google.genai import Client as GenaiClient
from google.genai.types import Content, EmbedContentConfig, Part
from qdrant_client import QdrantClient

# La función embed() se importa del módulo de proceso para garantizar
# que usamos exactamente el mismo pipeline de embedding tanto al indexar
# como al consultar.
from data.process.rag import embed

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_K = 5
DEFAULT_MIN_SCORE = 0.45  # Véase docs/rag/rag-design.md para justificación


# ---------------------------------------------------------------------------
# Configuración de clientes
# ---------------------------------------------------------------------------

def _load_env() -> None:
    env_path = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
    from pathlib import Path
    env_file = Path(__file__).resolve().parents[2] / "services" / "brasaland_api" / ".env"
    if env_file.exists():
        load_dotenv(env_file)


def _get_qdrant_client() -> QdrantClient:
    _load_env()
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def _get_genai_client() -> GenaiClient:
    _load_env()
    api_key = os.getenv("GEMINI_API_KEY", "")
    return GenaiClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    *,
    k: int = DEFAULT_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[dict[str, Any]]:
    """
    Fase 2a — Recuperación.

    Embebe la consulta, busca en Qdrant los k vecinos más cercanos y
    filtra los que estén por debajo de min_score.

    Devuelve una lista de payloads (NO objetos crudos del SDK de Qdrant)
    con los campos: source_document, section, text, chunk_index, score.

    Si ningún chunk supera el umbral, devuelve lista vacía.
    """
    if not query or not query.strip():
        return []

    # 1. Embeker la consulta (misma función embed() que en indexación)
    query_vector = embed(query.strip())

    # 2. Buscar en Qdrant
    client = _get_qdrant_client()
    collection = os.getenv("QDRANT_COLLECTION", "brasaland_knowledge")

    try:
        results = client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=k,
            with_payload=True,
        )
    except Exception:
        _logger.exception("Error al buscar en Qdrant")
        return []

    # 3. Filtrar por umbral y convertir a dicts planos
    filtered: list[dict[str, Any]] = []
    for hit in results:
        score = hit.score
        if score < min_score:
            continue
        payload = hit.payload or {}
        filtered.append({
            "source_document": payload.get("source_document", ""),
            "section": payload.get("section", ""),
            "text": payload.get("text", ""),
            "chunk_index": payload.get("chunk_index", -1),
            "score": round(score, 4),
        })

    return filtered


# ---------------------------------------------------------------------------
# Generación
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres Yayo, un vendedor entrenado de Brasaland, una cadena de restaurantes con 14 locales en Colombia y Florida.

Tu objetivo es responder preguntas de gerentes de local, empleados y clientes con la misma seguridad y precisión que un vendedor experimentado.

### Reglas obligatorias:

1. Responde SOLO con la información contenida en el contexto que se te proporciona debajo. No inventes datos, números, políticas o procedimientos que no aparezcan en el contexto.

2. Si en el contexto no hay información suficiente para responder la pregunta, responde honestamente: "No tengo información suficiente en la base de conocimiento para responder esa pregunta. Consulta con tu supervisor o escribe a [operaciones@brasaland.com/calidad@brasaland.com] según corresponda."

3. Mantén el idioma de la pregunta. Si te preguntan en español, respondes en español. Si te preguntan en inglés, respondes en inglés.

4. Si la pregunta es sobre alérgenos, usa EXACTAMENTE la redacción del documento fuente de alérgenos. Nunca respondas "sin riesgo" — si hay posibilidad de trazas, debes mencionarlo.

5. Conserva los montos en dólares y pesos colombianos tal como aparecen en el contexto. No hagas conversiones de moneda.

6. Si tu respuesta incluye datos numéricos (porcentajes, montos, kg), verifica que aparezcan textualmente en el contexto recuperado. Nunca uses un número que no esté en el contexto.

7. Responde de forma clara, directa y útil, como lo haría un vendedor que conoce bien los productos y procedimientos de Brasaland."""


def generate_answer(question: str, context: list[dict[str, Any]]) -> str:
    """
    Fase 2b — Generación de respuesta.

    Arma un prompt con el contexto recuperado (lista de chunks) y llama
    al LLM de generación para producir una respuesta en lenguaje natural.

    Args:
        question: La pregunta original del usuario.
        context: Lista de payloads devuelta por retrieve().

    Returns:
        Respuesta generada por el LLM como string.
    """
    # Armar el bloque de contexto
    if not context:
        context_block = "No se encontraron fragmentos relevantes en la base de conocimiento."
    else:
        context_lines = []
        for i, chunk in enumerate(context, 1):
            source = chunk.get("source_document", "?")
            section = chunk.get("section", "?")
            text = chunk.get("text", "")
            context_lines.append(f"[{i}] Documento: {source} | Sección: {section}\n{text}\n")
        context_block = "\n---\n".join(context_lines)

    prompt = f"""Contexto recuperado de la base de conocimiento de Brasaland:

{context_block}

---
Pregunta del usuario: {question}

---

Basándote ÚNICAMENTE en el contexto anterior, genera una respuesta clara y precisa como vendedor de Brasaland."""

    # Llamar al LLM de generación (modelo separado del de embeddings)
    client = _get_genai_client()
    model = os.getenv("LLM_MODEL_ID", "gemini-2.0-flash")

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                Content(role="user", parts=[Part(text=SYSTEM_PROMPT)]),
                Content(role="user", parts=[Part(text=prompt)]),
            ],
        )
        return response.text
    except Exception:
        _logger.exception("Error al llamar al LLM de generación")
        return "Lo siento, hubo un error al generar la respuesta. Intenta de nuevo más tarde."


# ---------------------------------------------------------------------------
# Query (punto de entrada único para consumidores externos)
# ---------------------------------------------------------------------------

def query(question: str) -> str:
    """
    Fase 2 — Pipeline RAG completo.

    Orquesta retrieve() → generate_answer() y devuelve la respuesta final.

    Esta es la ÚNICA función que deben llamar consumidores externos
    (endpoints, scripts, agentes).

    Args:
        question: Pregunta en lenguaje natural del usuario.

    Returns:
        Respuesta generada por el LLM basada en el contexto recuperado.
    """
    # 1. Recuperar fragmentos relevantes
    chunks = retrieve(question)

    # 2. Generar respuesta a partir del contexto
    answer = generate_answer(question, chunks)

    return answer


# ---------------------------------------------------------------------------
# CLI de prueba
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    if len(sys.argv) < 2:
        print("Uso: uv run python data/pipelines/rag.py '¿tu pregunta?'")
        sys.exit(1)

    question = sys.argv[1]
    answer = query(question)
    print(f"\nPregunta: {question}")
    print(f"Respuesta: {answer}")