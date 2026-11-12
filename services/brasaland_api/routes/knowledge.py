#!/usr/bin/env python3
"""
services/brasaland_api/routes/knowledge.py — Endpoint de consulta RAG.

Exposición:
  POST /knowledge/query  →  { "answer": "..." }

Nunca devuelve chunks crudos al cliente. La generación ocurre en
data/pipelines/rag.py; este router solo importa y llama a query().
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from data.pipelines.rag import query as rag_query

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
)


# ── Modelos de request / response ──────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


# ── Endpoint ───────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
def knowledge_query(payload: QueryRequest) -> QueryResponse:
    """
    Responde una pregunta en lenguaje natural usando la base de conocimiento
    de Brasaland.

    El endpoint:
      1. Recibe una pregunta.
      2. Llama a data/pipelines/rag.query() que orquesta retrieve + generate.
      3. Devuelve SOLO la respuesta generada (nunca chunks crudos).

    Los logs del servidor pueden incluir detalles de recuperación
    para depuración interna.
    """
    _logger.debug("Pregunta recibida: %s", payload.question[:80])

    answer = rag_query(payload.question)

    _logger.debug("Respuesta generada (%d caracteres)", len(answer))
    return QueryResponse(answer=answer)