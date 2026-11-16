"""Grafo LangGraph del pipeline rfp_intake.

Construye un grafo dirigido con los nodos:
  pdf_to_markdown → compute_readability → classifier
    → (si válida) orchestrator → workers (paralelo) → synthesizer → persist
    → (si inválida) persist (status=descartado)

Uso desde el router:
    from data.pipelines.rfp_intake.graph import run_rfp_intake
    state = run_rfp_intake(ticket_id=42, pdf_path="/data/raw/solicitud.pdf")
"""

from __future__ import annotations

import logging
from typing import Any

from data.pipelines.rfp_intake.nodes import (
    classifier,
    compute_readability,
    orchestrator,
    pdf_to_markdown,
    persist_ticket,
    synthesizer,
    worker_marketing,
    worker_operaciones,
    worker_procurement,
    worker_training,
)
from data.pipelines.rfp_intake.state import RFPIntakeState

_logger = logging.getLogger(__name__)


def run_rfp_intake(ticket_id: int, pdf_path: str) -> dict[str, Any]:
    """Ejecuta el pipeline completo de recepción RFP.

    Args:
        ticket_id: ID del ticket en PostgreSQL.
        pdf_path: Ruta absoluta o relativa al PDF subido.

    Returns:
        Dict con el estado final del pipeline, incluyendo:
          - success: bool
          - ticket_id: int
          - status: str (analisis_completo | descartado)
          - summary: str | None (solo si analisis_completo)
          - error: str | None (si hubo fallo)
    """
    state = RFPIntakeState(ticket_id=ticket_id, pdf_path=pdf_path)

    try:
        # ─── Nodo 1: PDF → Markdown ──────────────────────────────────
        state = pdf_to_markdown(state)
        if state.error:
            _logger.error("Fallo en pdf_to_markdown: %s", state.error)
            persist_ticket(state)
            return _result(state, success=False)

        # ─── Nodo 1b: Legibilidad ────────────────────────────────────
        state = compute_readability(state)
        if state.error:
            _logger.warning("Fallo en compute_readability (no crítico): %s", state.error)
            # No detenemos el pipeline por fallo de legibilidad

        # ─── Nodo 2: Clasificador ────────────────────────────────────
        state = classifier(state)
        if state.error:
            _logger.error("Fallo en classifier: %s", state.error)
            persist_ticket(state)
            return _result(state, success=False)

        # Si no es válido, persistimos y terminamos
        if not state.is_valid:
            persist_ticket(state)
            return _result(state, success=True)

        # ─── Nodo 3: Orquestador ────────────────────────────────────
        state = orchestrator(state)
        if state.error:
            _logger.error("Fallo en orchestrator: %s", state.error)
            persist_ticket(state)
            return _result(state, success=False)

        # ─── Nodo 4: Workers (solo los departamentos necesarios) ────
        dept_functions = {
            "marketing": worker_marketing,
            "operaciones": worker_operaciones,
            "procurement": worker_procurement,
            "training": worker_training,
        }

        needed = state.rfp_metadata.departments_needed if state.rfp_metadata else []
        for dept_id in needed:
            if dept_id in dept_functions:
                state = dept_functions[dept_id](state)
                _logger.info("Worker %s completado", dept_id)

        # ─── Nodo 5: Synthesizer ─────────────────────────────────────
        state = synthesizer(state)
        if state.error:
            _logger.error("Fallo en synthesizer: %s", state.error)

        # ─── Persistir resultados ────────────────────────────────────
        persist_ticket(state)

        return _result(state, success=True)

    except Exception as exc:
        _logger.exception("Error inesperado en pipeline rfp_intake: %s", exc)
        state.error = str(exc)
        state.error_node = "unknown"
        try:
            persist_ticket(state)
        except Exception as persist_exc:
            _logger.exception("Error adicional al persistir tras fallo: %s", persist_exc)
        return _result(state, success=False)


def _result(state: RFPIntakeState, success: bool) -> dict[str, Any]:
    """Convierte el estado final en un dict de resultado."""
    status = "descartado"
    if state.is_valid and state.final_summary:
        status = "analisis_completo"
    elif state.is_valid is False:
        status = "descartado"

    return {
        "success": success,
        "ticket_id": state.ticket_id,
        "status": status,
        "summary": state.final_summary,
        "error": state.error,
        "departments_analyzed": (
            [a.department_id for a in state.department_analyses]
            if state.department_analyses else []
        ),
        "readability": {
            "flesch_reading_ease": state.readability.flesch_reading_ease if state.readability else None,
            "flesch_kincaid_grade": state.readability.flesch_kincaid_grade if state.readability else None,
            "gunning_fog": state.readability.gunning_fog if state.readability else None,
            "word_count": state.readability.word_count if state.readability else None,
        } if state.readability else None,
    }