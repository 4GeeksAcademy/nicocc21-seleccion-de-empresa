"""
services/brasaland_api/routes/agent.py — Consulta de traces del agente de soporte.

Exposición:
  GET /agent/traces/{run_id}  →  trace completo de una corrida del grafo.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agents.support_agent import tracing

router = APIRouter(prefix="/agent", tags=["agent"])


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


@router.get("/traces/{run_id}", response_model=TraceResponse)
def get_agent_trace(run_id: str) -> TraceResponse:
    trace = tracing.get_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TRACE_NOT_FOUND")
    return TraceResponse.model_validate(trace)
