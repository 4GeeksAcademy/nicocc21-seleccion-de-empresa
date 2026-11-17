"""services/brasaland_api/routes/rfp_response.py — Endpoints de generación de respuesta (Hito 9, Parte 2).

Endpoints:
  POST /rfp/{ticket_id}/generate  → Dispara el pipeline generador-evaluador
  GET  /rfp/{ticket_id}/response  → Obtiene el resultado completo (borradores + evaluaciones)
  GET  /rfp/{ticket_id}/response/{department_id} → Obtiene el resultado de un departamento

La generación es async: responde rápido (202 + status), corre el pipeline en
background, la UI hace polling del estado.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from services.brasaland_api.database import get_db
from data.pipelines.rfp_response import approval as approval_module
from services.brasaland_api.rfp_models import (
    DepartmentSection,
    RFPMetadata,
    Ticket,
)

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rfp",
    tags=["rfp", "response"],
)


# ─── Schemas de request/response ──────────────────────────────────────


class EvaluationResultSchema(BaseModel):
    evaluator_id: str
    passed: bool
    score: float | None = None
    feedback: str = ""
    details: dict[str, Any] | None = None


class DepartmentResponseSchema(BaseModel):
    department_id: str
    status: str
    iterations_used: int
    needs_human_review: bool
    draft_content: str | None = None
    evaluations: list[EvaluationResultSchema] = []
    key_aspects: dict[str, Any] | None = None


class GenerateResponseSchema(BaseModel):
    ticket_id: int
    status: str
    message: str


class ResponseResultSchema(BaseModel):
    ticket_id: int
    status: str
    departments: list[DepartmentResponseSchema] = []
    error_message: str | None = None


# ─── Helpers ──────────────────────────────────────────────────────────


def _execute_response_pipeline(ticket_id: int) -> None:
    """Ejecuta el pipeline de generación en un hilo separado."""
    try:
        from data.pipelines.rfp_response import run_rfp_response_pipeline
        result = run_rfp_response_pipeline(ticket_id=ticket_id)
        _logger.info(
            "Pipeline de respuesta completado para ticket %d: "
            "status=%s, success=%s",
            ticket_id, result.get("status"), result.get("success"),
        )
        if result.get("needs_human_review"):
            _logger.warning(
                "Ticket %d tiene departamentos que requieren revisión humana: %s",
                ticket_id, result["needs_human_review"],
            )
    except Exception as exc:
        _logger.exception(
            "Error al ejecutar pipeline de respuesta para ticket %d: %s",
            ticket_id, exc,
        )
        # Marcar ticket con error
        try:
            from sqlmodel import Session
            from services.brasaland_api.database import engine
            with Session(engine) as session:
                ticket = session.get(Ticket, ticket_id)
                if ticket:
                    ticket.status = "needs_human_review"
                    ticket.error_message = (
                        f"Pipeline response error: {exc}"
                    )
                    session.add(ticket)
                    session.commit()
        except Exception as db_exc:
            _logger.exception(
                "Error al persistir fallo del pipeline response: %s",
                db_exc,
            )


def _evaluation_from_orm(
    section: DepartmentSection,
) -> list[EvaluationResultSchema]:
    """Convierte evaluation_results de ORM a schema."""
    evals = []
    if section.evaluation_results:
        for raw in section.evaluation_results:
            if isinstance(raw, dict):
                evals.append(EvaluationResultSchema(
                    evaluator_id=raw.get("evaluator_id", "unknown"),
                    passed=raw.get("passed", False),
                    score=raw.get("score"),
                    feedback=raw.get("feedback", ""),
                    details=raw.get("details"),
                ))
    return evals


# ─── Endpoints ────────────────────────────────────────────────────────


@router.post(
    "/{ticket_id}/generate",
    response_model=GenerateResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_response(
    ticket_id: int,
    session: Session = Depends(get_db),
) -> GenerateResponseSchema:
    """Dispara el pipeline generador-evaluador para un ticket.

    El ticket debe estar en estado 'analisis_completo' (handoff de Parte 1).
    El pipeline corre en background; la UI debe hacer polling del estado.

    Args:
        ticket_id: ID del ticket a procesar.

    Returns:
        202 Accepted con estado inicial.
    """
    # Verificar que el ticket existe
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} no encontrado",
        )

    # Validar estado
    if ticket.status not in (
        "analisis_completo",
        "generando_borrador",
        "en_evaluacion",
        "needs_human_review",
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Ticket en estado '{ticket.status}'. "
                f"Se esperaba 'analisis_completo', 'generando_borrador', "
                f"'en_evaluacion' o 'needs_human_review'."
            ),
        )

    # Si ya está en proceso, no re-disparar
    if ticket.status in ("generando_borrador", "en_evaluacion"):
        return GenerateResponseSchema(
            ticket_id=ticket_id,
            status=ticket.status,
            message=f"Ticket #{ticket_id} ya está siendo procesado.",
        )

    # Resetear estado si viene de needs_human_review (re-generación)
    if ticket.status == "needs_human_review":
        ticket.status = "generando_borrador"
        session.add(ticket)
        session.commit()
        _logger.info(
            "Ticket %d re-generado desde needs_human_review",
            ticket_id,
        )

    # Disparar pipeline en background
    thread = threading.Thread(
        target=_execute_response_pipeline,
        args=(ticket_id,),
        daemon=True,
    )
    thread.start()

    _logger.info(
        "Pipeline de respuesta disparado para ticket %d",
        ticket_id,
    )

    return GenerateResponseSchema(
        ticket_id=ticket_id,
        status="generando_borrador",
        message=(
            f"Generación de respuesta iniciada para ticket #{ticket_id}. "
            f"Consultar GET /rfp/{{ticket_id}} para estado actual."
        ),
    )


@router.get(
    "/{ticket_id}/response",
    response_model=ResponseResultSchema,
)
def get_response_result(
    ticket_id: int,
    session: Session = Depends(get_db),
) -> ResponseResultSchema:
    """Obtiene el resultado completo de la generación de respuesta.

    Incluye borradores y evaluaciones por departamento.
    """
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} no encontrado",
        )

    # Obtener secciones por departamento
    sections = session.exec(
        select(DepartmentSection).where(
            DepartmentSection.ticket_id == ticket_id
        )
    ).all()

    departments = []
    for section in sections:
        # Solo incluir secciones que tengan draft_content (Parte 2)
        if not section.draft_content:
            continue

        key_aspects = None
        if section.key_aspects:
            try:
                key_aspects = json.loads(section.key_aspects)
            except (json.JSONDecodeError, TypeError):
                key_aspects = {"raw": section.key_aspects}

        # Determinar iteraciones usadas (desde evaluation_results)
        iterations_used = 1
        needs_review = section.approval_status == "request_changes"

        departments.append(DepartmentResponseSchema(
            department_id=section.department_id,
            status=section.approval_status,
            iterations_used=iterations_used,
            needs_human_review=needs_review,
            draft_content=section.draft_content,
            evaluations=_evaluation_from_orm(section),
            key_aspects=key_aspects,
        ))

    return ResponseResultSchema(
        ticket_id=ticket_id,
        status=ticket.status,
        departments=departments,
        error_message=ticket.error_message,
    )


@router.get(
    "/{ticket_id}/response/{department_id}",
    response_model=DepartmentResponseSchema,
)
def get_department_response(
    ticket_id: int,
    department_id: str,
    session: Session = Depends(get_db),
) -> DepartmentResponseSchema:
    """Obtiene el resultado de generación para un departamento específico."""
    section = session.exec(
        select(DepartmentSection).where(
            DepartmentSection.ticket_id == ticket_id,
            DepartmentSection.department_id == department_id,
        )
    ).first()

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Departamento '{department_id}' no encontrado "
                f"para ticket {ticket_id}"
            ),
        )

    key_aspects = None
    if section.key_aspects:
        try:
            key_aspects = json.loads(section.key_aspects)
        except (json.JSONDecodeError, TypeError):
            key_aspects = {"raw": section.key_aspects}

    return DepartmentResponseSchema(
        department_id=section.department_id,
        status=section.approval_status,
        iterations_used=1,
        needs_human_review=section.approval_status == "request_changes",
        draft_content=section.draft_content,
        evaluations=_evaluation_from_orm(section),
        key_aspects=key_aspects,
    )

# ═══════════════════════════════════════════════════════════════════════════
#  Endpoints de aprobación humana (Hito 9, Parte 3)
# ═══════════════════════════════════════════════════════════════════════════


class ApprovalActionRequest(BaseModel):
    """Request para registrar una acción de aprobación."""
    department_id: str
    action: str  # "approve" | "reject" | "request_changes"
    comments: str = ""


class ApprovalActionResponse(BaseModel):
    """Respuesta con el estado actualizado tras una acción."""
    success: bool
    ticket_id: int
    approval_status: str
    state: dict


class ApprovalStateResponse(BaseModel):
    """Respuesta con el estado de aprobación completo."""
    success: bool
    ticket_id: int
    approval_status: str
    state: dict


class ConflictResolutionRequest(BaseModel):
    """Request para resolver un conflicto."""
    conflict_trigger_id: str
    resolution: str


@router.post(
    "/{ticket_id}/approve",
    response_model=ApprovalActionResponse,
)
def record_approval_endpoint(
    ticket_id: int,
    body: ApprovalActionRequest,
) -> ApprovalActionResponse:
    """Registra la acción de un humano sobre una aprobación de departamento.

    Args:
        ticket_id: ID del ticket.
        body.department_id: "marketing" | "operaciones" | "procurement" | "training" | "ceo".
        body.action: "approve" | "reject" | "request_changes".
        body.comments: Comentarios opcionales.

    Returns:
        Estado actualizado del ApprovalState.
    """
    from data.pipelines.rfp_response.approval import record_approval

    try:
        result = record_approval(
            ticket_id=ticket_id,
            department_id=body.department_id,
            action=body.action,
            comments=body.comments,
        )
        return ApprovalActionResponse(
            success=True,
            ticket_id=ticket_id,
            approval_status=result.get("status", "unknown"),
            state=result,
        )
    except ValueError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/{ticket_id}/resolve-conflict",
    response_model=ApprovalStateResponse,
)
def resolve_conflict_endpoint(
    ticket_id: int,
    body: ConflictResolutionRequest,
) -> ApprovalStateResponse:
    """Resuelve un conflicto usando el árbitro fijo (BRIEFING §7).

    Args:
        ticket_id: ID del ticket.
        body.conflict_trigger_id: ID del trigger a resolver.
        body.resolution: Decisión del árbitro.

    Returns:
        ApprovalState actualizado.
    """
    from data.pipelines.rfp_response.approval import (
        load_checkpoint,
        resolve_conflict,
    )

    approval_state = load_checkpoint(ticket_id)
    if approval_state is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay checkpoint para ticket {ticket_id}. "
                   f"Ejecutar run_approval_pipeline primero.",
        )

    try:
        approval_state = resolve_conflict(
            approval_state=approval_state,
            conflict_trigger_id=body.conflict_trigger_id,
            resolution=body.resolution,
        )
        from data.pipelines.rfp_response.approval import approval_state_to_dict
        return ApprovalStateResponse(
            success=True,
            ticket_id=ticket_id,
            approval_status=approval_state.status,
            state=approval_state_to_dict(approval_state),
        )
    except ValueError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{ticket_id}/approval-state",
    response_model=ApprovalStateResponse,
)
def get_approval_state_endpoint(
    ticket_id: int,
) -> ApprovalStateResponse:
    """Obtiene el estado de aprobación actual de un ticket."""
    from data.pipelines.rfp_response.approval import (
        approval_state_to_dict,
        load_checkpoint,
    )

    approval_state = load_checkpoint(ticket_id)
    if approval_state is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay checkpoint para ticket {ticket_id}. "
                   f"Ejecutar run_approval_pipeline primero.",
        )

    return ApprovalStateResponse(
        success=True,
        ticket_id=ticket_id,
        approval_status=approval_state.status,
        state=approval_state_to_dict(approval_state),
    )


@router.post(
    "/{ticket_id}/start-approval",
    response_model=ApprovalStateResponse,
)
def start_approval_pipeline_endpoint(
    ticket_id: int,
) -> ApprovalStateResponse:
    """Inicia el pipeline de aprobación para un ticket.

    El ticket debe estar en estado 'esperando_aprobacion'.
    """
    from data.pipelines.rfp_response.approval import (
        approval_state_to_dict,
        run_approval_pipeline,
    )

    try:
        result = run_approval_pipeline(ticket_id=ticket_id)
        if not result.get("success"):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.get("error", "Error desconocido"),
            )
        return ApprovalStateResponse(
            success=True,
            ticket_id=ticket_id,
            approval_status=result["approval_status"],
            state=result["approvals"],
        )
    except ValueError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
