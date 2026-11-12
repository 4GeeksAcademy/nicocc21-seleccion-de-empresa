#!/usr/bin/env python3
"""
services/brasaland_api/routes/knowledge.py — Endpoint de consulta RAG.

Exposición:
  POST /knowledge/query  →  { "answer": "...", "run_id": "..." }

Nunca devuelve chunks crudos al cliente. La pregunta se resuelve con el grafo
de LangGraph de agents/support_agent/, que reutiliza data/pipelines/rag.py.
El trace de cada corrida se consulta en GET /agent/traces/{run_id}.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from agents.support_agent import run_agent

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
    run_id: str


# ── Endpoint ───────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
def knowledge_query(payload: QueryRequest) -> QueryResponse:
    """
    Responde una pregunta en lenguaje natural usando la base de conocimiento
    de Brasaland.

    El endpoint:
      1. Recibe una pregunta.
      2. Ejecuta el grafo del agente de soporte (retrieve → generate | no_context).
      3. Devuelve SOLO la respuesta generada (nunca chunks crudos) y el run_id
         para consultar el trace de la corrida.
    """
    _logger.debug("Pregunta recibida: %s", payload.question[:80])

    result = run_agent(payload.question)

    _logger.debug("Respuesta generada (run_id=%s, %d caracteres)", result.run_id, len(result.answer))
    return QueryResponse(answer=result.answer, run_id=result.run_id)