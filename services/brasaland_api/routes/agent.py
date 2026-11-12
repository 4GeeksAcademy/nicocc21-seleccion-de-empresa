"""
services/brasaland_api/routes/agent.py — Endpoints del agente de soporte (LangGraph).

Exposición:
  POST /agent/query                        →  { "answer": "...", "run_id": "..." }
  GET  /agent/traces/{run_id}              →  trace completo de una corrida
  GET  /agent/traces/{run_id}/checkpoints  →  transiciones guardadas por el checkpointer

Este router no contiene lógica de negocio: solo invoca el grafo y traduce el
resultado a HTTP. Los errores internos nunca se exponen al cliente; el detalle
queda en el trace consultable por `run_id`.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.brasaland_api.agent import AgentRunError, list_checkpoints, run_agent
from services.brasaland_api.agent import tracing

_logger = logging.getLogger(__name__)

AGENT_FAILURE_MESSAGE = (
    "El agente no pudo procesar la pregunta en este momento. "
    "Inténtalo de nuevo más tarde."
)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    question: str


class AgentQueryResponse(BaseModel):
    answer: str
    run_id: str


class AgentErrorResponse(BaseModel):
    detail: str
    run_id: str


class TraceStep(BaseModel):
    kind: str
    name: str
    started_at: str
    duration_ms: float
    input: dict[str, Any]
    output: Any
    error: str | None


class TraceResponse(BaseModel):
    run_id: str
    question: str
    status: str
    started_at: str
    finished_at: str | None
    answer: str | None
    error: str | None
    steps: list[TraceStep]


class CheckpointResponse(BaseModel):
    checkpoint_id: str
    step: int | None
    source: str | None
    next: list[str]
    state_keys: list[str]
    created_at: str | None


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    responses={400: {"model": AgentErrorResponse}, 503: {"model": AgentErrorResponse}},
)
def agent_query(payload: AgentQueryRequest) -> AgentQueryResponse | JSONResponse:
    try:
        result = run_agent(payload.question)
    except AgentRunError as exc:
        _logger.exception("Fallo del agente en la corrida %s", exc.run_id)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": AGENT_FAILURE_MESSAGE, "run_id": exc.run_id},
        )

    if result.error is not None or result.answer is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": result.error, "run_id": result.run_id},
        )
    return AgentQueryResponse(answer=result.answer, run_id=result.run_id)


@router.get("/traces/{run_id}", response_model=TraceResponse)
def get_agent_trace(run_id: str) -> TraceResponse:
    trace = tracing.get_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TRACE_NOT_FOUND")
    return TraceResponse.model_validate(trace)


@router.get("/traces/{run_id}/checkpoints", response_model=list[CheckpointResponse])
def get_agent_checkpoints(run_id: str) -> list[CheckpointResponse]:
    checkpoints = list_checkpoints(run_id)
    if not checkpoints:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CHECKPOINTS_NOT_FOUND")
    return [CheckpointResponse.model_validate(item) for item in checkpoints]
