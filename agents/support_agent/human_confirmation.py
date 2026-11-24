"""
human_confirmation.py — Gates de confirmación humana para acciones irreversibles.

Según el briefing de seguridad de Brasaland (sección 5), las siguientes
acciones REQUIEREN confirmación humana explícita:

  1. Enviar campaña de marketing/notificación push a toda la base de clientes.
  2. Aprobar pedido a proveedor > umbral de costo (2 días de consumo promedio).
  3. Ajustar o anular puntos Brasa Points de un cliente.
  4. Dar de baja o modificar estado de un proveedor.

Además, cualquier acción del agente que tenga impacto económico directo
debe ser confirmada por un humano antes de ejecutarse.

Uso:
    from agents.support_agent.human_confirmation import (
        require_confirmation,
        ActionType,
        ActionRequest,
    )

    # En una tool del agente:
    result = require_confirmation(
        action_type=ActionType.CREATE_PURCHASE_ORDER,
        description="Pedido a Proveedor X por $1,200 USD",
        estimated_impact="$1,200 USD",
    )
    if not result.approved:
        return "Acción no aprobada. Se requiere revisión humana."
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Tipos de acción
# ──────────────────────────────────────────────


class ActionType(enum.Enum):
    """Tipos de acción que requieren confirmación humana."""

    SEND_MARKETING_CAMPAIGN = "send_marketing_campaign"
    """Enviar campaña de marketing o notificación push a toda la base."""

    APPROVE_PURCHASE_ORDER = "approve_purchase_order"
    """Aprobar un pedido a proveedor (evaluar umbral)."""

    ADJUST_LOYALTY_POINTS = "adjust_loyalty_points"
    """Ajustar o anular puntos Brasa Points de un cliente."""

    MODIFY_SUPPLIER_STATUS = "modify_supplier_status"
    """Dar de baja o modificar el estado de un proveedor."""

    CREATE_PURCHASE_ORDER = "create_purchase_order"
    """Crear un pedido nuevo a proveedor."""

    MODIFY_INVENTORY = "modify_inventory"
    """Modificar niveles de inventario (escritura)."""

    # Acciones del Hito 9 (flujo agéntico RFP)
    APPROVE_RFP_SECTION = "approve_rfp_section"
    """Aprobar sección de propuesta RFP (por departamento)."""

    GENERATE_FINAL_DOCUMENT = "generate_final_document"
    """Generar documento final de propuesta (>$50k USD requiere CEO)."""


# ──────────────────────────────────────────────
# Configuración de umbrales
# ──────────────────────────────────────────────


class ThresholdConfig:
    """Umbrales para determinar qué acciones requieren confirmación.

    Los valores deben ser ajustados por el equipo de operaciones según
    el volumen y costos reales de Brasaland.
    """

    # Costo máximo que puede aprobar el agente automáticamente
    # Equivale a ~2 días de consumo promedio de un ingrediente.
    AUTO_APPROVE_MAX_COST_USD: float = 500.0

    # Umbral para pedidos a proveedor que requieren confirmación
    PURCHASE_ORDER_THRESHOLD_USD: float = 1000.0

    # Puntos Brasa Points: cualquier ajuste requiere confirmación
    LOYALTY_POINTS_REQUIRE_CONFIRMATION: bool = True

    # Cambio de estado de proveedor: siempre requiere confirmación
    SUPPLIER_STATUS_CHANGE_REQUIRES_CONFIRMATION: bool = True


# ──────────────────────────────────────────────
# Resultados
# ──────────────────────────────────────────────


@dataclass
class ConfirmationResult:
    """Resultado de una solicitud de confirmación humana."""

    approved: bool
    """True si la acción fue aprobada."""

    action_type: ActionType
    """Tipo de acción solicitada."""

    description: str
    """Descripción legible de la acción."""

    requested_at: float = field(default_factory=time.time)
    """Timestamp de la solicitud."""

    confirmed_by: str | None = None
    """Nombre/rol de la persona que aprobó (None si pendiente)."""

    reason: str | None = None
    """Razón de la aprobación o rechazo."""


# ──────────────────────────────────────────────
# Evaluador de umbrales
# ──────────────────────────────────────────────


def requires_confirmation(
    action_type: ActionType,
    estimated_cost_usd: float | None = None,
) -> bool:
    """Determina si una acción requiere confirmación humana.

    Args:
        action_type: Tipo de acción a evaluar.
        estimated_cost_usd: Costo estimado en USD (si aplica).

    Returns:
        True si la acción requiere confirmación humana.
    """
    config = ThresholdConfig()

    # Acciones que SIEMPRE requieren confirmación
    always_require: set[ActionType] = {
        ActionType.SEND_MARKETING_CAMPAIGN,
        ActionType.ADJUST_LOYALTY_POINTS,
        ActionType.MODIFY_SUPPLIER_STATUS,
        ActionType.GENERATE_FINAL_DOCUMENT,
    }

    if action_type in always_require:
        return True

    # Acciones que dependen del umbral de costo
    if action_type in (ActionType.APPROVE_PURCHASE_ORDER, ActionType.CREATE_PURCHASE_ORDER):
        if estimated_cost_usd is not None and estimated_cost_usd > config.AUTO_APPROVE_MAX_COST_USD:
            return True
        # Si no tenemos costo estimado, requerimos confirmación por precaución
        if estimated_cost_usd is None:
            return True

    # Acciones de inventario: cualquier escritura requiere confirmación
    if action_type == ActionType.MODIFY_INVENTORY:
        return True

    # Acciones RFP: aprobación por departamento siempre requiere humano
    if action_type == ActionType.APPROVE_RFP_SECTION:
        return True

    return False


def format_confirmation_message(
    action_type: ActionType,
    description: str,
    estimated_impact: str | None = None,
) -> str:
    """Genera un mensaje legible para la solicitud de confirmación.

    Args:
        action_type: Tipo de acción.
        description: Descripción de la acción.
        estimated_impact: Impacto estimado (económico, operativo, etc.).

    Returns:
        Mensaje formateado para el usuario/humano revisor.
    """
    action_names = {
        ActionType.SEND_MARKETING_CAMPAIGN: "📢 Campaña de Marketing",
        ActionType.APPROVE_PURCHASE_ORDER: "📦 Aprobar Pedido a Proveedor",
        ActionType.ADJUST_LOYALTY_POINTS: "⭐ Ajuste de Brasa Points",
        ActionType.MODIFY_SUPPLIER_STATUS: "🏢 Cambio de Estado de Proveedor",
        ActionType.CREATE_PURCHASE_ORDER: "📦 Nuevo Pedido a Proveedor",
        ActionType.MODIFY_INVENTORY: "📋 Modificación de Inventario",
        ActionType.APPROVE_RFP_SECTION: "📄 Aprobar Sección de Propuesta",
        ActionType.GENERATE_FINAL_DOCUMENT: "📑 Generar Documento Final",
    }

    msg_parts = [
        f"⚠️  **CONFIRMACIÓN REQUERIDA**: {action_names.get(action_type, action_type.value)}",
        f"",
        f"**Descripción:** {description}",
    ]

    if estimated_impact:
        msg_parts.append(f"**Impacto estimado:** {estimated_impact}")

    msg_parts.extend([
        f"",
        f"Esta acción requiere aprobación humana antes de ejecutarse.",
        f"Responde 'sí' para aprobar, 'no' para rechazar.",
    ])

    return "\n".join(msg_parts)


# ──────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────


def require_confirmation(
    action_type: ActionType,
    description: str,
    estimated_cost_usd: float | None = None,
    estimated_impact: str | None = None,
) -> ConfirmationResult:
    """Evalúa si una acción requiere confirmación humana.

    Si el umbral lo requiere, retorna un resultado pendiente.
    La confirmación real debe ser recogida por el flujo del agente.

    Args:
        action_type: Tipo de acción.
        description: Descripción legible.
        estimated_cost_usd: Costo estimado en USD.
        estimated_impact: Impacto estimado (texto libre).

    Returns:
        ConfirmationResult con el estado de la solicitud.
    """
    _logger.info(
        "Evaluando confirmación para action_type=%s, cost=%s, desc=%r",
        action_type.value,
        estimated_cost_usd,
        description[:100],
    )

    if not requires_confirmation(action_type, estimated_cost_usd):
        _logger.info(
            "Acción %s no requiere confirmación (bajo umbral)",
            action_type.value,
        )
        return ConfirmationResult(
            approved=True,
            action_type=action_type,
            description=description,
            reason="Auto-aprobado: bajo umbral de costo o acción de bajo riesgo.",
        )

    _logger.warning(
        "Acción %s REQUIERE confirmación humana: %s",
        action_type.value,
        description[:150],
    )

    # Devolver resultado no aprobado — el agente debe pausar y preguntar
    return ConfirmationResult(
        approved=False,
        action_type=action_type,
        description=description,
        reason="Pendiente de confirmación humana.",
    )