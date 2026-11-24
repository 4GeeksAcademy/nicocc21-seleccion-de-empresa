"""
services/brasaland_api/routes/rfp.py — Endpoints de recepción de RFP (Hito 9).

Endpoints:
  POST   /rfp/upload       → Subir PDF, crear ticket, disparar pipeline async
  GET    /rfp/{ticket_id}   → Estado del ticket
  GET    /rfp/{ticket_id}/result → Resultado completo (metadatos + key_aspects)

La subida es async: responde rápido (202 + ticket_id), corre el pipeline en
background, la UI hace polling del estado.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from services.brasaland_api.database import get_db
from services.brasaland_api.notifications import get_notification_manager
from services.brasaland_api.rfp_models import (
    DepartmentSection,
    RFPMetadata,
    Ticket,
    ensure_rfp_tables,
)

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rfp",
    tags=["rfp"],
)

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


# ─── Schemas de request/response ──────────────────────────────────────

class TicketResponse(BaseModel):
    ticket_id: int
    status: str
    rfp_external_id: str | None = None
    created_at: str
    updated_at: str
    error_message: str | None = None


class DepartmentSectionResponse(BaseModel):
    department_id: str
    key_aspects: dict[str, Any] | None = None
    approval_status: str


class RFPResultResponse(BaseModel):
    ticket_id: int
    status: str
    metadata: dict[str, Any] | None = None
    departments: list[DepartmentSectionResponse] = []
    readability: dict[str, Any] | None = None
    summary: str | None = None
    error_message: str | None = None


class UploadResponse(BaseModel):
    ticket_id: int
    status: str
    message: str


# ─── Helpers ──────────────────────────────────────────────────────────

def _execute_pipeline(ticket_id: int, pdf_path: str) -> None:
    """Ejecuta el pipeline rfp_intake en un hilo separado.

    Corre en background para que el POST responda rápido.
    """
    try:
        from data.pipelines.rfp_intake import run_rfp_intake
        result = run_rfp_intake(ticket_id=ticket_id, pdf_path=pdf_path)
        _logger.info(
            "Pipeline completado para ticket %d: status=%s, success=%s",
            ticket_id, result.get("status"), result.get("success"),
        )
    except Exception as exc:
        _logger.exception("Error al ejecutar pipeline para ticket %d: %s", ticket_id, exc)
        # Si falla el pipeline, actualizar ticket a descartado con error
        try:
            from sqlmodel import Session
            from services.brasaland_api.database import engine
            with Session(engine) as session:
                ticket = session.get(Ticket, ticket_id)
                if ticket:
                    ticket.status = "descartado"
                    ticket.error_message = f"Pipeline error: {exc}"
                    session.add(ticket)
                    session.commit()
        except Exception as db_exc:
            _logger.exception("Error al persistir fallo del pipeline: %s", db_exc)


def _ticket_to_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        rfp_external_id=ticket.rfp_external_id,
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else "",
        error_message=ticket.error_message,
    )


# ─── Endpoints ────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_rfp(
    file: UploadFile,
    rfp_external_id: str | None = None,
    session: Session = Depends(get_db),
) -> UploadResponse:
    """Sube un PDF de RFP, crea un ticket y dispara el pipeline en background.

    Args:
        file: Archivo PDF de la RFP.
        rfp_external_id: Identificador externo opcional (ej. número de referencia).

    Returns:
        202 Accepted con ticket_id para hacer polling del estado.
    """
    # Validar que sea PDF
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos PDF",
        )

    # Asegurar que las tablas existan
    ensure_rfp_tables()

    # Crear ticket en estado analizando
    ticket = Ticket(
        rfp_external_id=rfp_external_id,
        status="analizando",
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    # Guardar PDF en data/raw/
    raw_filename = f"rfp_{ticket.id}_{uuid4().hex[:8]}_{file.filename}"
    raw_path = RAW_DIR / raw_filename
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with raw_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        session.delete(ticket)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al guardar el PDF: {exc}",
        )

    # Actualizar ticket con la ruta del PDF
    ticket.raw_pdf_path = str(raw_path)
    session.add(ticket)
    session.commit()

    # Publicar evento SSE: notificar a los clientes conectados
    try:
        manager = get_notification_manager()
        rfp_id = f"rfp_{ticket.id:04d}"
        manager.publish("rfp", "rfp_ticket_created", {
            "ticket_id": f"tkt_{ticket.id:04d}",
            "rfp_id": rfp_id,
            "status": ticket.status,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        })
        _logger.info("Evento SSE rfp_ticket_created publicado para ticket %d", ticket.id)
    except Exception:
        _logger.exception("Error al publicar evento SSE para ticket %d — continuando", ticket.id)

    # Disparar pipeline en background
    thread = threading.Thread(
        target=_execute_pipeline,
        args=(ticket.id, str(raw_path)),
        daemon=True,
    )
    thread.start()

    _logger.info("Ticket %d creado: %s", ticket.id, raw_filename)

    return UploadResponse(
        ticket_id=ticket.id,
        status="analizando",
        message=f"RFP recibida. Ticket #{ticket.id} en proceso.",
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, session: Session = Depends(get_db)) -> TicketResponse:
    """Obtiene el estado actual de un ticket."""
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} no encontrado",
        )
    return _ticket_to_response(ticket)


@router.get("/{ticket_id}/result", response_model=RFPResultResponse)
def get_ticket_result(
    ticket_id: int, session: Session = Depends(get_db),
) -> RFPResultResponse:
    """Obtiene el resultado completo del análisis de una RFP."""
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} no encontrado",
        )

    # Obtener metadatos
    metadata_obj = session.exec(
        select(RFPMetadata).where(RFPMetadata.ticket_id == ticket_id)
    ).first()

    # Obtener secciones por departamento
    sections = session.exec(
        select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)
    ).all()

    metadata_dict: dict[str, Any] | None = None
    if metadata_obj:
        metadata_dict = {
            "client_name": metadata_obj.client_name,
            "location": metadata_obj.location,
            "service_type": metadata_obj.service_type,
            "scope": metadata_obj.scope,
            "deadline": metadata_obj.deadline,
            "budget_range": metadata_obj.budget_range,
            "budget_min_usd": metadata_obj.budget_min_usd,
            "budget_max_usd": metadata_obj.budget_max_usd,
            "departments_needed": json.loads(metadata_obj.departments_needed) if metadata_obj.departments_needed else [],
        }

    readability_dict: dict[str, Any] | None = None
    if metadata_obj:
        readability_dict = {
            "flesch_reading_ease": metadata_obj.flesch_reading_ease,
            "flesch_kincaid_grade": metadata_obj.flesch_kincaid_grade,
            "gunning_fog": metadata_obj.gunning_fog,
            "word_count": metadata_obj.word_count,
            "sentence_count": metadata_obj.sentence_count,
        }

    departments = []
    for section in sections:
        key_aspects = None
        if section.key_aspects:
            try:
                key_aspects = json.loads(section.key_aspects)
            except json.JSONDecodeError:
                key_aspects = {"raw": section.key_aspects}

        departments.append(DepartmentSectionResponse(
            department_id=section.department_id,
            key_aspects=key_aspects,
            approval_status=section.approval_status,
        ))

    # Construir summary (solo si está completo)
    summary = None
    if ticket.status == "analisis_completo" and metadata_dict:
        lines = [
            f"Cliente: {metadata_dict.get('client_name') or 'N/A'}",
            f"Ubicación: {metadata_dict.get('location') or 'N/A'}",
            f"Servicio: {metadata_dict.get('service_type') or 'N/A'}",
            f"Alcance: {metadata_dict.get('scope') or 'N/A'}",
            f"Fecha límite: {metadata_dict.get('deadline') or 'N/A'}",
            f"Presupuesto: {metadata_dict.get('budget_range') or 'N/A'}",
            "",
            "Departamentos analizados:",
        ]
        for dept in departments:
            lines.append(f"- {dept.department_id}")
            if dept.key_aspects and dept.key_aspects.get("extractos_relevantes"):
                lines.append(f"  Extractos: {len(dept.key_aspects['extractos_relevantes'])}")
        summary = "\n".join(lines)

    return RFPResultResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        metadata=metadata_dict,
        departments=departments,
        readability=readability_dict,
        summary=summary,
        error_message=ticket.error_message,
    )