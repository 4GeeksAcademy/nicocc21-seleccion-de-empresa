"""data/pipelines/rfp_response/approval.py — Aprobación humana, arbitraje y síntesis (Hito 9, Parte 3).

Flujo:
  1. initialize_approval_state() — Crea ApprovalState desde RFPResponseState
  2. check_arbitration_triggers() — Detecta conflictos entre departamentos
  3. resolve_conflict() — Nodo de arbitraje con árbitro fijo (BRIEFING §7)
  4. synthesize_final_document() — Ultimate Document Synthesizer
  5. run_approval_pipeline() — Orquestador completo

Checkpointer:
  - SQLite local en data/checkpoints/rfp_approval.db
  - Cada interrupt() persiste ApprovalState para reanudar exactamente donde quedó
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from data.pipelines.rfp_response.state import (
    ApprovalEntry,
    ApprovalState,
    ConflictEntry,
    DepartmentResponse,
    FinalDocument,
    RFPResponseState,
)

_logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "checkpoints"
CHECKPOINT_DB = CHECKPOINT_DIR / "rfp_approval.db"

CEO_THRESHOLD_USD = 50000.0
MAX_APPROVAL_ITERATIONS = 5  # Límite de ciclos de aprobación/request_changes


# Registry de aprobadores (BRIEFING §2.1)
APPROVERS = {
    "marketing": "Camila Ospina",
    "operaciones": "Felipe Guerrero",
    "procurement": "Lucía Fernández",
    "training": "Jake Morrison",
}

# Registry de nombres de departamento
DEPARTMENT_NAMES = {
    "marketing": "Marketing y Experiencia Digital",
    "operaciones": "Operaciones de Restaurante",
    "procurement": "Procurement y Proveedores",
    "training": "Training y Estándares de Calidad",
}

# Árbitros fijos por trigger (BRIEFING §7)
ARBITERS = {
    "cost-vs-feasibility": "Camila Ospina",
    "setup-sla-breach": "Felipe Guerrero",
    "ceo-threshold": "Mariana Restrepo",
}

# Reglas de resolución por trigger
ARBITRATION_RULES = {
    "cost-vs-feasibility": (
        "Subir precio o reducir alcance; forzar request_changes "
        "en la(s) sección(es) desalineada(s)."
    ),
    "setup-sla-breach": (
        "Forzar request_changes hasta >= 10 días hábiles en todas partes."
    ),
    "ceo-threshold": (
        "Bloquear ultimate synthesizer hasta approve de CEO; "
        "ruta de rechazo si la CEO rechaza."
    ),
}


# ═══════════════════════════════════════════════════════════════════════
#  Inicialización
# ═══════════════════════════════════════════════════════════════════════


def initialize_approval_state(
    state: RFPResponseState,
) -> ApprovalState:
    """Crea el ApprovalState desde el RFPResponseState de la Parte 2.

    Args:
        state: RFPResponseState despu\u00e9s de la Parte 2 (status=esperando_aprobacion).

    Returns:
        ApprovalState con aprobaciones por departamento + CEO si aplica.
    """
    approvals: dict[str, ApprovalEntry] = {}

    for dept in state.departments:
        approver = APPROVERS.get(dept.department_id, "Responsable desconocido")
        entry = ApprovalEntry(
            department_id=dept.department_id,
            approver=approver,
            status="pendiente",
        )
        approvals[dept.department_id] = entry

    # Verificar CEO threshold (BRIEFING §5, regla 6)
    ceo_pending = _check_ceo_threshold(state)
    ceo_entry: Optional[ApprovalEntry] = None
    if ceo_pending:
        ceo_entry = ApprovalEntry(
            department_id="ceo",
            approver="Mariana Restrepo",
            status="pendiente",
        )

    # Detectar conflictos iniciales
    conflicts = check_arbitration_triggers(state)

    approval_state = ApprovalState(
        ticket_id=state.ticket_id,
        approvals=approvals,
        ceo_approval_pending=ceo_pending,
        ceo_approval=ceo_entry,
        conflicts=conflicts,
        status="pending_approvals",
    )

    return approval_state


def _check_ceo_threshold(state: RFPResponseState) -> bool:
    """Determina si el valor estimado supera $50K USD/a\u00f1o (BRIEFING §5, regla 6).

    Revisa budget_max_usd en los metadatos de la RFP.
    """
    metadata = state.rfp_metadata or {}
    budget_max = metadata.get("budget_max_usd")
    budget_range = metadata.get("budget_range", "")

    # Si budget_max_usd está explícito
    if budget_max is not None and budget_max > CEO_THRESHOLD_USD:
        return True

    # Fallback: parsear budget_range string
    if budget_range:
        numbers = re.findall(r'[\d,]+', budget_range.replace(",", ""))
        for num_str in numbers:
            try:
                val = float(num_str.replace(",", ""))
                if val > CEO_THRESHOLD_USD:
                    return True
            except ValueError:
                continue

    return False


# ═══════════════════════════════════════════════════════════════════════
#  Checkpointer SQLite
# ═══════════════════════════════════════════════════════════════════════


def _ensure_checkpoint_db() -> None:
    """Asegura que el directorio y tabla de checkpoints existan."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_checkpoints (
                ticket_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_checkpoint(approval_state: ApprovalState) -> None:
    """Persiste el ApprovalState en el checkpointer SQLite."""
    _ensure_checkpoint_db()

    state_dict = {
        "ticket_id": approval_state.ticket_id,
        "status": approval_state.status,
        "ceo_approval_pending": approval_state.ceo_approval_pending,
        "iteration_count": approval_state.iteration_count,
        "max_iterations": approval_state.max_iterations,
        "approvals": {
            dept_id: {
                "department_id": entry.department_id,
                "approver": entry.approver,
                "status": entry.status,
                "approved_at": entry.approved_at,
                "comments": entry.comments,
            }
            for dept_id, entry in approval_state.approvals.items()
        },
        "conflicts": [
            {
                "trigger_id": c.trigger_id,
                "description": c.description,
                "department_ids": c.department_ids,
                "arbiter": c.arbiter,
                "status": c.status,
                "resolution": c.resolution,
            }
            for c in approval_state.conflicts
        ],
    }

    if approval_state.ceo_approval:
        state_dict["ceo_approval"] = {
            "department_id": approval_state.ceo_approval.department_id,
            "approver": approval_state.ceo_approval.approver,
            "status": approval_state.ceo_approval.status,
            "approved_at": approval_state.ceo_approval.approved_at,
            "comments": approval_state.ceo_approval.comments,
        }

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(CHECKPOINT_DB))
    try:
        conn.execute(
            """INSERT OR REPLACE INTO approval_checkpoints (ticket_id, state_json, updated_at)
               VALUES (?, ?, ?)""",
            (approval_state.ticket_id, json.dumps(state_dict), now),
        )
        conn.commit()
    finally:
        conn.close()


def load_checkpoint(ticket_id: int) -> Optional[ApprovalState]:
    """Carga el ApprovalState desde el checkpointer SQLite."""
    _ensure_checkpoint_db()

    conn = sqlite3.connect(str(CHECKPOINT_DB))
    try:
        cursor = conn.execute(
            "SELECT state_json FROM approval_checkpoints WHERE ticket_id = ?",
            (ticket_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        state_dict = json.loads(row[0])

        approvals = {}
        for dept_id, entry_dict in state_dict.get("approvals", {}).items():
            approvals[dept_id] = ApprovalEntry(
                department_id=entry_dict["department_id"],
                approver=entry_dict["approver"],
                status=entry_dict.get("status", "pendiente"),
                approved_at=entry_dict.get("approved_at"),
                comments=entry_dict.get("comments", ""),
            )

        conflicts = []
        for c_dict in state_dict.get("conflicts", []):
            conflicts.append(ConflictEntry(
                trigger_id=c_dict["trigger_id"],
                description=c_dict.get("description", ""),
                department_ids=c_dict.get("department_ids", []),
                arbiter=c_dict.get("arbiter", ""),
                status=c_dict.get("status", "pendiente"),
                resolution=c_dict.get("resolution", ""),
            ))

        ceo_approval = None
        if state_dict.get("ceo_approval"):
            ceo_dict = state_dict["ceo_approval"]
            ceo_approval = ApprovalEntry(
                department_id=ceo_dict["department_id"],
                approver=ceo_dict["approver"],
                status=ceo_dict.get("status", "pendiente"),
                approved_at=ceo_dict.get("approved_at"),
                comments=ceo_dict.get("comments", ""),
            )

        return ApprovalState(
            ticket_id=state_dict["ticket_id"],
            approvals=approvals,
            ceo_approval_pending=state_dict.get("ceo_approval_pending", False),
            ceo_approval=ceo_approval,
            conflicts=conflicts,
            status=state_dict.get("status", "pending_approvals"),
            iteration_count=state_dict.get("iteration_count", 0),
            max_iterations=state_dict.get("max_iterations", 5),
        )
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
#  Aprobación humana
# ═══════════════════════════════════════════════════════════════════════


def record_approval(
    ticket_id: int,
    department_id: str,
    action: str,
    comments: str = "",
) -> dict[str, Any]:
    """Registra la acción de un humano sobre una aprobación de departamento.

    Args:
        ticket_id: ID del ticket.
        department_id: ID del departamento (o "ceo").
        action: "approve" | "reject" | "request_changes".
        comments: Comentarios del aprobador.

    Returns:
        Dict con el estado actualizado del ApprovalState.
    """
    approval_state = load_checkpoint(ticket_id)
    if approval_state is None:
        raise ValueError(
            f"No hay checkpoint para ticket {ticket_id}. "
            "Ejecutar run_approval_pipeline primero."
        )

    if department_id == "ceo":
        if approval_state.ceo_approval is None:
            raise ValueError(
                f"Ticket {ticket_id} no requiere aprobación de CEO."
            )
        entry = approval_state.ceo_approval
    elif department_id in approval_state.approvals:
        entry = approval_state.approvals[department_id]
    else:
        raise ValueError(
            f"Departamento '{department_id}' no encontrado en approval_state."
        )

    if action == "approve":
        entry.status = "aprobado"
        entry.approved_at = datetime.now(timezone.utc).isoformat()
        entry.comments = comments
    elif action == "reject":
        entry.status = "rechazado"
        entry.approved_at = datetime.now(timezone.utc).isoformat()
        entry.comments = comments
    elif action == "request_changes":
        entry.status = "request_changes"
        entry.comments = comments
        approval_state.iteration_count += 1  # Contar iteración
    else:
        raise ValueError(
            f"Acción inválida: '{action}'. "
            "Usar approve, reject o request_changes."
        )

    # Si CEO aprueba/rechaza, actualizar flag
    if department_id == "ceo":
        if action in ("approve", "reject"):
            approval_state.ceo_approval_pending = False
        if action == "approve":
            # Resolver automáticamente conflicto ceo-threshold si existe
            for conflict in approval_state.conflicts:
                if conflict.trigger_id == "ceo-threshold" and conflict.status == "pendiente":
                    conflict.status = "resuelto"
                    conflict.resolution = "CEO aprobó el presupuesto excedente"
                    break
        if action == "reject":
            approval_state.status = "rejected"

    # Verificar límite de iteraciones (Corrección 3)
    if approval_state.iteration_count >= MAX_APPROVAL_ITERATIONS:
        approval_state.status = "rejected"
        save_checkpoint(approval_state)
        _sync_ticket_status(approval_state)
        return approval_state_to_dict(approval_state)

    # Verificar si todas las aprobaciones están completas
    _update_global_status(approval_state)

    # Persistir checkpoint
    save_checkpoint(approval_state)

    # Actualizar ticket en DB si el estado final es "completed" o "rejected" (Corrección 2)
    _sync_ticket_status(approval_state)

    return approval_state_to_dict(approval_state)


def _update_global_status(approval_state: ApprovalState) -> None:
    """Actualiza el estado global del ApprovalState seg\u00fan las aprobaciones actuales."""
    all_approved = all(
        entry.status == "aprobado"
        for entry in approval_state.approvals.values()
    )

    any_rejected = any(
        entry.status == "rechazado"
        for entry in approval_state.approvals.values()
    )

    any_request_changes = any(
        entry.status == "request_changes"
        for entry in approval_state.approvals.values()
    )

    if any_rejected:
        approval_state.status = "rejected"
        return

    if any_request_changes:
        approval_state.status = "pending_approvals"
        return

    if not all_approved:
        approval_state.status = "pending_approvals"
        return

    # Todos los departamentos aprobados
    if approval_state.ceo_approval_pending:
        approval_state.status = "waiting_ceo"
        return

    # Verificar si hay conflictos sin resolver
    unresolved = [c for c in approval_state.conflicts if c.status != "resuelto"]
    if unresolved:
        approval_state.status = "arbitrating"
        return

    approval_state.status = "completed"


def approval_state_to_dict(approval_state: ApprovalState) -> dict[str, Any]:
    """Convierte ApprovalState a dict para respuesta API."""
    result: dict[str, Any] = {
        "ticket_id": approval_state.ticket_id,
        "status": approval_state.status,
        "approvals": {
            dept_id: {
                "department_id": entry.department_id,
                "approver": entry.approver,
                "status": entry.status,
                "approved_at": entry.approved_at,
                "comments": entry.comments,
            }
            for dept_id, entry in approval_state.approvals.items()
        },
        "ceo_approval_pending": approval_state.ceo_approval_pending,
        "conflicts": [
            {
                "trigger_id": c.trigger_id,
                "description": c.description,
                "department_ids": c.department_ids,
                "arbiter": c.arbiter,
                "status": c.status,
                "resolution": c.resolution,
            }
            for c in approval_state.conflicts
        ],
    }

    if approval_state.ceo_approval:
        result["ceo_approval"] = {
            "department_id": approval_state.ceo_approval.department_id,
            "approver": approval_state.ceo_approval.approver,
            "status": approval_state.ceo_approval.status,
            "approved_at": approval_state.ceo_approval.approved_at,
            "comments": approval_state.ceo_approval.comments,
        }

    return result


# ═══════════════════════════════════════════════════════════════════════
#  Arbitraje
# ═══════════════════════════════════════════════════════════════════════


def check_arbitration_triggers(
    state: RFPResponseState,
) -> list[ConflictEntry]:
    """Eval\u00faa los 3 triggers de conflicto del BRIEFING §7.

    Args:
        state: RFPResponseState con los departamentos y sus drafts.

    Returns:
        Lista de ConflictEntry detectados (vac\u00eda si no hay conflictos).
    """
    conflicts: list[ConflictEntry] = []

    # Trigger 1: cost-vs-feasibility
    conflicts.extend(_check_cost_vs_feasibility(state))

    # Trigger 2: setup-sla-breach
    conflicts.extend(_check_setup_sla_breach(state))

    # Trigger 3: ceo-threshold
    if _check_ceo_threshold(state):
        ceo_conflict = ConflictEntry(
            trigger_id="ceo-threshold",
            description=(
                "El valor anual estimado de la propuesta supera los $50,000 USD. "
                "Se requiere aprobaci\u00f3n de Mariana Restrepo (CEO) "
                "antes de la s\u00edntesis final."
            ),
            department_ids=["ceo"],
            arbiter=ARBITERS["ceo-threshold"],
            status="pendiente",
        )
        # Solo añadir si no existe ya uno igual
        if not any(c.trigger_id == "ceo-threshold" for c in conflicts):
            conflicts.append(ceo_conflict)

    return conflicts


def _check_cost_vs_feasibility(state: RFPResponseState) -> list[ConflictEntry]:
    """Verifica si el costo estimado de procurement es coherente con operaciones.

    Regla: Si procurement estima un costo de insumos y operaciones un precio
    por evento/cubierto, y la relaci\u00f3n no es viable, se dispara el trigger.
    """
    conflicts: list[ConflictEntry] = []
    procurement_dept = _find_dept(state, "procurement")
    operaciones_dept = _find_dept(state, "operaciones")

    if not procurement_dept or not operaciones_dept:
        return conflicts

    if not procurement_dept.final_draft or not operaciones_dept.final_draft:
        return conflicts

    procurement_numbers = re.findall(r'[\d,.]+', procurement_dept.final_draft)
    operaciones_numbers = re.findall(r'[\d,.]+', operaciones_dept.final_draft)

    proc_cost = _extract_largest_number(procurement_numbers)
    op_price = _extract_largest_number(operaciones_numbers)

    if proc_cost and op_price and proc_cost > op_price * 0.7:
        conflicts.append(ConflictEntry(
            trigger_id="cost-vs-feasibility",
            description=(
                f"El costo estimado de insumos ({proc_cost}) no soporta "
                f"el precio por evento ({op_price}) de Operaciones. "
                "Margen insuficiente (< 30%)."
            ),
            department_ids=["procurement", "operaciones"],
            arbiter=ARBITERS["cost-vs-feasibility"],
            status="pendiente",
        ))

    return conflicts


def _check_setup_sla_breach(state: RFPResponseState) -> list[ConflictEntry]:
    """Verifica que ninguna secci\u00f3n prometa tiempos menores a 10 d\u00edas h\u00e1biles.

    BRIEFING §5, regla 3.
    """
    conflicts: list[ConflictEntry] = []

    time_patterns = [
        r'(\d+)\s*d[\w]*\s*(?:h[\w]*\s*)?(?:de\s*)?(?:montaje|entrega|instalaci[óo]n|implementaci[óo]n|setup)',
        r'(?:montaje|entrega|instalaci[óo]n|implementaci[óo]n|setup).*?(\d+)\s*d[\w]*\s*(?:h[\w]*\s*)?',
        r'entregamos?\s*(?:en\s*)?(\d+)\s*d[\w]*\s*(?:h[\w]*\s*)?',
        r'(?:listos?|preparados?)\s*(?:en\s*)?(\d+)\s*d[\w]*\s*(?:h[\w]*\s*)?',
    ]

    for dept in state.departments:
        if not dept.final_draft:
            continue

        draft_lower = dept.final_draft.lower()
        for pattern in time_patterns:
            matches = re.findall(pattern, draft_lower)
            for days_str in matches:
                try:
                    days = int(days_str)
                    if days < 10:
                        conflicts.append(ConflictEntry(
                            trigger_id="setup-sla-breach",
                            description=(
                                f"Departamento '{dept.department_id}' promete "
                                f"{days} d\u00edas h\u00e1biles ({days} < 10). "
                                "Viola BRIEFING \u00a75, regla 3."
                            ),
                            department_ids=[dept.department_id],
                            arbiter=ARBITERS["setup-sla-breach"],
                            status="pendiente",
                        ))
                        break  # Solo un conflicto por departamento
                except ValueError:
                    continue

    return conflicts


def _extract_largest_number(numbers: list[str]) -> Optional[float]:
    """Extrae el n\u00famero m\u00e1s grande de una lista de strings num\u00e9ricos."""
    max_val: Optional[float] = None
    for num_str in numbers:
        try:
            val = float(num_str.replace(",", ""))
            if max_val is None or val > max_val:
                max_val = val
        except ValueError:
            continue
    return max_val


def _find_dept(
    state: RFPResponseState, dept_id: str
) -> Optional[DepartmentResponse]:
    """Busca un departamento por ID en el estado."""
    for dept in state.departments:
        if dept.department_id == dept_id:
            return dept
    return None


def resolve_conflict(
    approval_state: ApprovalState,
    conflict_trigger_id: str,
    resolution: str,
) -> ApprovalState:
    """Resuelve un conflicto usando el \u00e1rbitro fijo (BRIEFING §7).

    Args:
        approval_state: Estado actual de aprobaciones.
        conflict_trigger_id: ID del trigger a resolver.
        resolution: Decisi\u00f3n del \u00e1rbitro.

    Returns:
        ApprovalState actualizado.
    """
    found = False
    for conflict in approval_state.conflicts:
        if conflict.trigger_id == conflict_trigger_id and conflict.status == "pendiente":
            conflict.status = "resuelto"
            conflict.resolution = resolution
            found = True

            # Aplicar regla de resolución
            if conflict.trigger_id == "setup-sla-breach":
                for dept_id in conflict.department_ids:
                    if dept_id in approval_state.approvals:
                        approval_state.approvals[dept_id].status = "request_changes"
                        existing = approval_state.approvals[dept_id].comments
                        prefix = f"[Árbitro: {conflict.arbiter}] {resolution}"
                        approval_state.approvals[dept_id].comments = (
                            f"{prefix}\n{existing}" if existing else prefix
                        )

            break

    if not found:
        raise ValueError(
            f"Conflicto '{conflict_trigger_id}' no encontrado o ya resuelto."
        )

    _update_global_status(approval_state)
    save_checkpoint(approval_state)
    return approval_state


# ═══════════════════════════════════════════════════════════════════════
#  Síntesis del documento final
# ═══════════════════════════════════════════════════════════════════════


def synthesize_final_document(
    state: RFPResponseState,
    approval_state: ApprovalState,
) -> FinalDocument:
    """Ultimate Document Synthesizer.

    Compila las secciones aprobadas de cada departamento en un documento final.

    Args:
        state: RFPResponseState con drafts.
        approval_state: ApprovalState con todas las aprobaciones.

    Returns:
        FinalDocument con todas las secciones compiladas.

    Raises:
        ValueError: Si no todos los departamentos est\u00e1n aprobados.
    """
    for dept_id, entry in approval_state.approvals.items():
        if entry.status != "aprobado":
            raise ValueError(
                f"No se puede sintetizar: departamento '{dept_id}' "
                f"est\u00e1 en estado '{entry.status}' (requiere 'aprobado')."
            )

    if approval_state.ceo_approval_pending:
        raise ValueError(
            "No se puede sintetizar: aprobaci\u00f3n de CEO pendiente."
        )

    sections: dict[str, str] = {}
    for dept in state.departments:
        if dept.final_draft and dept.department_id in approval_state.approvals:
            sections[dept.department_id] = dept.final_draft

    total_value = None
    if state.rfp_metadata:
        total_value = state.rfp_metadata.get("budget_max_usd")

    now = datetime.now(timezone.utc).isoformat()

    return FinalDocument(
        ticket_id=state.ticket_id,
        sections=sections,
        total_estimated_value=total_value,
        generated_at=now,
        delivery_status="pendiente",
    )


def format_final_document(document: FinalDocument) -> str:
    """Formatea el documento final como texto legible para Ventas."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  PROPUESTA ECONÓMICA — BRASALAND")
    lines.append(f"  Ticket #{document.ticket_id}")
    lines.append(f"  Generado: {document.generated_at or 'N/A'}")
    if document.total_estimated_value:
        lines.append(
            f"  Valor estimado: ${document.total_estimated_value:,.2f} USD"
        )
    lines.append("=" * 70)
    lines.append("")
    lines.append("CONTENIDO DE LA PROPUESTA")
    lines.append("-" * 70)
    lines.append("")

    section_titles = {
        "marketing": "MARKETING Y EXPERIENCIA DIGITAL",
        "operaciones": "OPERACIONES DE RESTAURANTE",
        "procurement": "PROCUREMENT Y PROVEEDORES",
        "training": "TRAINING Y ESTÁNDARES DE CALIDAD",
    }

    for dept_id, content in document.sections.items():
        title = section_titles.get(dept_id, dept_id.upper())
        lines.append("")
        lines.append(f"--- {title} ---")
        lines.append("")
        lines.append(content.strip())
        lines.append("")
        lines.append("-" * 70)

    lines.append("")
    lines.append("DOCUMENTO GENERADO AUTOMÁTICAMENTE")
    lines.append(
        "Requiere validaci\u00f3n del equipo de Ventas "
        "antes de env\u00edo al cliente."
    )
    lines.append("=" * 70)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  Pipeline orquestador
# ═══════════════════════════════════════════════════════════════════════


def run_approval_pipeline(
    ticket_id: int,
    db_session: Any = None,
) -> dict[str, Any]:
    """Orquestador de la Parte 3.

    Lee el ticket desde DB, inicializa ApprovalState, persiste checkpoint,
    y retorna el estado inicial para que los humanos aprueben v\u00eda API.

    Args:
        ticket_id: ID del ticket (debe estar en esperando_aprobacion).
        db_session: Sesión SQLModel opcional.

    Returns:
        Dict con estado de aprobaciones listas para human-in-the-loop.
    """
    from sqlmodel import Session, select as _sqlmodel_select

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
        # 1. Verificar ticket
        ticket = db_session.get(TicketORM, ticket_id)
        if ticket is None:
            return {"success": False, "error": f"Ticket {ticket_id} no encontrado"}

        if ticket.status not in (
            "esperando_aprobacion",
            "needs_human_review",
        ):
            return {
                "success": False,
                "error": (
                    f"Ticket en estado '{ticket.status}'. "
                    "Se esperaba 'esperando_aprobacion' o 'needs_human_review'."
                ),
            }

        # 2. Cargar metadatos
        metadata_obj = db_session.exec(
            _sqlmodel_select(RFPMetadataORM).where(
                RFPMetadataORM.ticket_id == ticket_id
            )
        ).first()

        # 3. Cargar secciones por departamento
        sections = db_session.exec(
            _sqlmodel_select(DepartmentSectionORM).where(
                DepartmentSectionORM.ticket_id == ticket_id
            )
        ).all()

        # 4. Reconstruir RFPResponseState desde DB
        metadata_dict = _metadata_to_dict(metadata_obj) if metadata_obj else {}
        departments_needed = (
            json.loads(
                metadata_obj.departments_needed
                if isinstance(metadata_obj.departments_needed, str)
                else metadata_obj.departments_needed
            )
            if metadata_obj
            else []
        )

        department_responses: list[DepartmentResponse] = []
        section_map: dict[str, DepartmentSectionORM] = {}
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

            dept_metadata = dict(metadata_dict)
            dept_metadata["departamento"] = dept_id
            dept_metadata["departamento_nombre"] = DEPARTMENT_NAMES.get(
                dept_id, dept_id
            )
            dept_metadata["responsable"] = APPROVERS.get(dept_id, "")

            dept_resp = DepartmentResponse(
                department_id=dept_id,
                key_aspects=key_aspects,
                metadata=dept_metadata,
                final_draft=section.draft_content if section else None,
                status=section.approval_status if section else "pendiente",
            )
            department_responses.append(dept_resp)

        state = RFPResponseState(
            ticket_id=ticket_id,
            rfp_metadata=metadata_dict,
            departments=department_responses,
            status=ticket.status,
        )

        # 5. Inicializar approval state
        approval_state = initialize_approval_state(state)

        # 6. Actualizar ticket a esperando_aprobacion si no lo está
        if ticket.status != "esperando_aprobacion":
            ticket.status = "esperando_aprobacion"
            db_session.add(ticket)
            db_session.commit()

        # 7. Guardar checkpoint inicial
        save_checkpoint(approval_state)

        if own_session:
            db_session.close()

        return {
            "success": True,
            "ticket_id": ticket_id,
            "approval_status": approval_state.status,
            "approvals": approval_state_to_dict(approval_state),
        }

    except Exception as exc:
        _logger.exception(
            "Error en pipeline de aprobaci\u00f3n para ticket %d: %s",
            ticket_id, exc,
        )
        if own_session and db_session:
            db_session.close()
        return {"success": False, "error": str(exc)}


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

def _sync_ticket_status(approval_state: ApprovalState) -> None:
    """Actualiza el estado del ticket en la DB según el ApprovalState.

    Si el estado es "completed", cambia a "terminado".
    Si es "rejected", cambia a "rechazado".
    Esto asegura que el ticket progrese más allá de "esperando_aprobacion".
    """
    MAPPING = {
        "completed": "terminado",
        "rejected": "rechazado",
    }
    new_status = MAPPING.get(approval_state.status)
    if new_status is None:
        return  # pending_approvals, waiting_ceo, arbitrating — no cambiar

    try:
        from sqlmodel import Session
        from services.brasaland_api.database import engine
        from services.brasaland_api.rfp_models import Ticket as TicketORM

        with Session(engine) as session:
            ticket = session.get(TicketORM, approval_state.ticket_id)
            if ticket and ticket.status not in ("terminado", "rechazado"):
                ticket.status = new_status
                session.add(ticket)
                session.commit()
    except Exception as exc:
        _logger.warning(
            "No se pudo sync ticket %d a '%s': %s",
            approval_state.ticket_id, new_status, exc,
        )
