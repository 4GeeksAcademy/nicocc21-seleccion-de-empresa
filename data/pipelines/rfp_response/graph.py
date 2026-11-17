"""Grafo del pipeline rfp_response — Hito 9, Parte 2.

Construye el estado RFPResponseState a partir del handoff de la Parte 1
(ticket en estado analisis_completo) y ejecuta el ciclo generador-evaluador.

Uso desde el router:
    from data.pipelines.rfp_response.graph import run_rfp_response_pipeline
    result = run_rfp_response_pipeline(ticket_id=42)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlmodel import select as _sqlmodel_select

from data.pipelines.rfp_response.nodes import run_all_department_cycles
from data.pipelines.rfp_response.state import (
    DepartmentResponse,
    RFPResponseState,
)

_logger = logging.getLogger(__name__)

# ─── DEPARTAMENTOS REGISTRY (mismo que Parte 1) ────────────────────────

DEPARTMENTS_REGISTRY = {
    "marketing": {
        "name": "Marketing y Experiencia Digital",
        "responsable": "Camila Ospina",
    },
    "operaciones": {
        "name": "Operaciones de Restaurante",
        "responsable": "Felipe Guerrero",
    },
    "procurement": {
        "name": "Procurement y Proveedores",
        "responsable": "Lucía Fernández",
    },
    "training": {
        "name": "Training y Estándares de Calidad",
        "responsable": "Jake Morrison",
    },
}


def run_rfp_response_pipeline(
    ticket_id: int,
    db_session: Any = None,
) -> dict[str, Any]:
    """Ejecuta el pipeline de generación de respuesta para un ticket.

    Args:
        ticket_id: ID del ticket en estado analisis_completo.
        db_session: Sesión SQLModel opcional (si no se provee, abre una
                    propia usando el engine de la aplicación).

    Returns:
        Dict con:
          - success: bool
          - ticket_id: int
          - status: str (nuevo estado del ticket)
          - departments: list[dict] resumen por departamento
          - needs_human_review: list[str] deptos que requieren revisión
          - error: str | None
    """
    from sqlmodel import Session

    from services.brasaland_api.database import engine
    from services.brasaland_api.rfp_models import (
        DepartmentSection as DepartmentSectionORM,
        RFPMetadata as RFPMetadataORM,
        Ticket as TicketORM,
    )

    own_session = False
    if db_session is None:
        db_session = Session(engine)
        own_session = True

    try:
        # 1. Verificar que el ticket existe y está en estado correcto
        ticket = db_session.get(TicketORM, ticket_id)
        if ticket is None:
            return _error_result(ticket_id, f"Ticket {ticket_id} no encontrado")

        if ticket.status not in ("analisis_completo", "generando_borrador", "en_evaluacion"):
            return _error_result(
                ticket_id,
                f"Ticket en estado '{ticket.status}'. "
                f"Se esperaba 'analisis_completo', 'generando_borrador' "
                f"o 'en_evaluacion'.",
            )

        # 2. Obtener metadatos de la RFP usando SQLModel
        metadata_obj = db_session.exec(
            _sqlmodel_select(RFPMetadataORM).where(
                RFPMetadataORM.ticket_id == ticket_id
            )
        ).first()

        if metadata_obj is None:
            return _error_result(
                ticket_id, f"Metadatos no encontrados para ticket {ticket_id}",
            )

        # 3. Obtener secciones por departamento (key_aspects de Parte 1)
        sections = db_session.exec(
            _sqlmodel_select(DepartmentSectionORM).where(
                DepartmentSectionORM.ticket_id == ticket_id
            )
        ).all()

        if not sections:
            return _error_result(
                ticket_id,
                f"No hay secciones departamentales para ticket {ticket_id}. "
                f"Ejecutar Parte 1 primero.",
            )

        # 4. Construir el estado RFPResponseState
        metadata_dict = _metadata_to_dict(metadata_obj)
        departments_needed = json.loads(
            metadata_obj.departments_needed
                if isinstance(metadata_obj.departments_needed, str)
                else metadata_obj.departments_needed
        )

        department_responses: list[DepartmentResponse] = []
        section_map: dict[str, Any] = {}
        for section in sections:
            section_map[section.department_id] = section

        for dept_id in departments_needed:
            section = section_map.get(dept_id)
            key_aspects = None
            if section and section.key_aspects:
                try:
                    key_aspects = json.loads(section.key_aspects)
                except (json.JSONDecodeError, TypeError):
                    key_aspects = {"raw": str(section.key_aspects)}

            # Construir metadatos específicos para este departamento
            dept_metadata = dict(metadata_dict)
            dept_metadata["departamento"] = dept_id
            dept_metadata["departamento_nombre"] = (
                DEPARTMENTS_REGISTRY.get(dept_id, {}).get("name", dept_id)
            )
            dept_metadata["responsable"] = (
                DEPARTMENTS_REGISTRY.get(dept_id, {}).get("responsable", "")
            )

            dept_resp = DepartmentResponse(
                department_id=dept_id,
                key_aspects=key_aspects,
                metadata=dept_metadata,
            )
            department_responses.append(dept_resp)

        # 5. Crear estado e intentar conectar knowledge base
        state = RFPResponseState(
            ticket_id=ticket_id,
            rfp_metadata=metadata_dict,
            departments=department_responses,
        )

        _try_load_knowledge_base(state)

        # 6. Actualizar ticket a generando_borrador
        ticket.status = "generando_borrador"
        db_session.add(ticket)
        db_session.commit()

        # 7. Ejecutar ciclo generador-evaluador
        state = run_all_department_cycles(state)

        # 8. Persistir resultados
        _persist_response(state, db_session)

        if own_session:
            db_session.close()

        # 9. Resultado
        departments_summary = _build_departments_summary(state)
        needs_review = [
            d.department_id
            for d in state.departments
            if d.needs_human_review
        ]

        return {
            "success": True,
            "ticket_id": ticket_id,
            "status": state.status,
            "departments": departments_summary,
            "needs_human_review": needs_review,
            "error": state.global_error,
        }

    except Exception as exc:
        _logger.exception(
            "Error en pipeline rfp_response para ticket %d: %s",
            ticket_id, exc,
        )
        if own_session and db_session:
            db_session.close()
        return _error_result(ticket_id, str(exc))


def _metadata_to_dict(metadata_obj: Any) -> dict[str, Any]:
    """Convierte un objeto RFPMetadata ORM a diccionario."""
    return {
        "client_name": getattr(metadata_obj, "client_name", None),
        "location": getattr(metadata_obj, "location", None),
        "service_type": getattr(metadata_obj, "service_type", None),
        "scope": getattr(metadata_obj, "scope", None),
        "deadline": getattr(metadata_obj, "deadline", None),
        "budget_range": getattr(metadata_obj, "budget_range", None),
        "budget_min_usd": getattr(metadata_obj, "budget_min_usd", None),
        "budget_max_usd": getattr(metadata_obj, "budget_max_usd", None),
        "departments_needed": getattr(metadata_obj, "departments_needed", ""),
    }


def _try_load_knowledge_base(state: RFPResponseState) -> None:
    """Intenta cargar contexto de la knowledge base semántica.

    Es opcional — si no está disponible, se omite silenciosamente.
    """
    try:
        from data.pipelines.rag import query as rag_query

        # Consulta genérica sobre políticas de propuesta
        response = rag_query(
            "¿Cuáles son las políticas de Brasaland para propuestas "
            "comerciales, términos de marca, y requisitos de calidad?",
        )
        if response and response.get("answer"):
            state.knowledge_base_available = True
            state.knowledge_context = response["answer"]
            _logger.info(
                "Knowledge base cargada para ticket %d",
                state.ticket_id,
            )
        else:
            _logger.info(
                "Knowledge base disponible pero sin respuesta para ticket %d",
                state.ticket_id,
            )
    except ImportError:
        _logger.info(
            "Knowledge base no disponible (data.pipelines.rag no encontrado) "
            "para ticket %d",
            state.ticket_id,
        )
    except Exception as exc:
        _logger.warning(
            "Error al cargar knowledge base para ticket %d: %s",
            state.ticket_id, exc,
        )


def _persist_response(
    state: RFPResponseState,
    session: Any,
) -> None:
    """Persiste los resultados del pipeline en PostgreSQL.

    Actualiza:
      - Ticket.status
      - DepartmentSection.draft_content
      - DepartmentSection.evaluation_results
      - DepartmentSection.approval_status
    """
    from services.brasaland_api.rfp_models import (
        DepartmentSection as DepartmentSectionORM,
        Ticket as TicketORM,
    )

    # 1. Actualizar ticket
    ticket = session.get(TicketORM, state.ticket_id)
    if ticket:
        ticket.status = state.status
        session.add(ticket)

    # 2. Actualizar secciones por departamento
    for dept in state.departments:
        existing = session.exec(
            _sqlmodel_select(DepartmentSectionORM.id).where(
                DepartmentSectionORM.ticket_id == state.ticket_id,
                DepartmentSectionORM.department_id == dept.department_id,
            )
        ).first()

        eval_results = []
        if dept.final_evaluations:
            eval_results = [
                {
                    "evaluator_id": e.evaluator_id,
                    "passed": e.passed,
                    "score": e.score,
                    "feedback": e.feedback,
                    "details": e.details,
                }
                for e in dept.final_evaluations
            ]

        section = DepartmentSectionORM(
            ticket_id=state.ticket_id,
            department_id=dept.department_id,
            draft_content=dept.final_draft,
            evaluation_results=eval_results if eval_results else None,
            approval_status=dept.status if dept.status != "pendiente" else "pendiente",
        )

        if existing and hasattr(existing, "id"):
            section.id = existing.id
            session.merge(section)
        else:
            session.add(section)

    session.commit()
    _logger.info(
        "Respuesta persistida para ticket %d (status=%s)",
        state.ticket_id, state.status,
    )


def _build_departments_summary(state: RFPResponseState) -> list[dict]:
    """Construye un resumen del resultado por departamento."""
    summary = []
    for dept in state.departments:
        evals = []
        if dept.final_evaluations:
            evals = [
                {
                    "evaluator_id": e.evaluator_id,
                    "passed": e.passed,
                    "score": e.score,
                }
                for e in dept.final_evaluations
            ]

        summary.append({
            "department_id": dept.department_id,
            "status": dept.status,
            "iterations": dept.current_iteration,
            "needs_human_review": dept.needs_human_review,
            "evaluations": evals,
            "word_count": len(dept.final_draft.split())
                if dept.final_draft else 0,
        })
    return summary


def _error_result(ticket_id: int, error: str) -> dict[str, Any]:
    """Construye un resultado de error."""
    _logger.error("Pipeline rfp_response falló para ticket %d: %s", ticket_id, error)
    return {
        "success": False,
        "ticket_id": ticket_id,
        "status": "descartado",
        "departments": [],
        "needs_human_review": [],
        "error": error,
    }