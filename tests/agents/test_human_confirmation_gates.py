#!/usr/bin/env python3
"""
tests/agents/test_human_confirmation_gates.py — Verificación de confirmación humana.

Según el briefing de seguridad de Brasaland (sección 5) y el sistema implementado
en agents/support_agent/human_confirmation.py, las siguientes acciones REQUIEREN
confirmación humana explícita:

  1. Enviar campaña de marketing/notificación push a toda la base de clientes.
  2. Aprobar pedido a proveedor > umbral de costo ($500 USD).
  3. Ajustar o anular puntos Brasa Points de un cliente.
  4. Dar de baja o modificar estado de un proveedor.
  5. Modificar inventario (escritura).
  6. Generar documento final de propuesta (>$50k USD requiere CEO).

Verifica:
  - Que las acciones irreversibles listadas requieren confirmación.
  - Que acciones por debajo del umbral NO requieren confirmación.
  - Que el mensaje de confirmación se formatea correctamente.
"""

from __future__ import annotations

import pytest

from agents.support_agent.human_confirmation import (
    ActionType,
    ConfirmationResult,
    ThresholdConfig,
    format_confirmation_message,
    require_confirmation,
    requires_confirmation,
)


class TestRequiresConfirmation:
    """Verifica qué acciones requieren confirmación humana."""

    # ── Acciones que SIEMPRE requieren confirmación ────────────────────

    @pytest.mark.parametrize("action_type", [
        ActionType.SEND_MARKETING_CAMPAIGN,
        ActionType.ADJUST_LOYALTY_POINTS,
        ActionType.MODIFY_SUPPLIER_STATUS,
        ActionType.MODIFY_INVENTORY,
        ActionType.GENERATE_FINAL_DOCUMENT,
    ])
    def test_actions_that_always_require_confirmation(self, action_type):
        """
        Las acciones identificadas como irreversibles en el briefing
        (sección 5) DEBEN requerir confirmación humana siempre.
        """
        assert requires_confirmation(action_type), (
            f"{action_type.value} debería requerir confirmación siempre"
        )

    # ── Acciones que dependen del umbral de costo ──────────────────────

    def test_purchase_order_above_threshold_requires_confirmation(self):
        """
        Un pedido a proveedor por encima del umbral ($500 USD)
        debe requerir confirmación humana.
        """
        assert requires_confirmation(
            ActionType.CREATE_PURCHASE_ORDER,
            estimated_cost_usd=1200.0,
        ), (
            "Pedido a proveedor por $1,200 USD (> $500 umbral) "
            "debe requerir confirmación"
        )

    def test_purchase_order_at_threshold_requires_confirmation(self):
        """
        Un pedido exactamente al nivel del umbral debe requerir confirmación.
        """
        assert requires_confirmation(
            ActionType.CREATE_PURCHASE_ORDER,
            estimated_cost_usd=ThresholdConfig.AUTO_APPROVE_MAX_COST_USD,
        ), (
            f"Pedido exactamente al umbral "
            f"(${ThresholdConfig.AUTO_APPROVE_MAX_COST_USD}) debe requerir confirmación"
        )

    def test_purchase_order_below_threshold_does_not_require_confirmation(self):
        """
        Un pedido a proveedor por debajo del umbral ($500 USD)
        NO debe requerir confirmación humana.
        """
        assert not requires_confirmation(
            ActionType.CREATE_PURCHASE_ORDER,
            estimated_cost_usd=100.0,
        ), (
            "Pedido a proveedor por $100 USD (< $500 umbral) "
            "NO debe requerir confirmación"
        )

    def test_purchase_order_without_cost_requires_confirmation(self):
        """
        Un pedido sin costo estimado debe requerir confirmación
        por precaución (principio de mínimo riesgo).
        """
        assert requires_confirmation(
            ActionType.CREATE_PURCHASE_ORDER,
            estimated_cost_usd=None,
        ), (
            "Pedido sin costo estimado debe requerir confirmación por precaución"
        )

    # ── Acciones que NUNCA requieren confirmación (por ahora) ───────────

    def test_unknown_action_type_does_not_require_confirmation(self):
        """
        Un tipo de acción no contemplado explícitamente no requiere
        confirmación humana.
        """
        assert not requires_confirmation(
            ActionType.APPROVE_RFP_SECTION,  # Esta tiene su propio flujo
        ), (
            "APPROVE_RFP_SECTION requiere confirmación por su diseño específico"
        )


class TestRequireConfirmationFunction:
    """Verifica el flujo completo de require_confirmation()."""

    def test_marketing_campaign_returns_not_approved(self):
        """SEND_MARKETING_CAMPAIGN debe devolver un resultado no aprobado."""
        result = require_confirmation(
            action_type=ActionType.SEND_MARKETING_CAMPAIGN,
            description="Campaña de verano para toda la base de clientes",
            estimated_impact="$5,000 USD estimados",
        )
        assert not result.approved, (
            "La campaña de marketing no debe estar auto-aprobada"
        )
        assert result.action_type == ActionType.SEND_MARKETING_CAMPAIGN
        assert "Campaña de verano" in result.description
        assert result.reason == "Pendiente de confirmación humana."

    def test_low_cost_action_returns_approved(self):
        """
        Una acción por debajo del umbral debe devolver
        un resultado aprobado automáticamente.
        """
        result = require_confirmation(
            action_type=ActionType.CREATE_PURCHASE_ORDER,
            description="Pedido de 10kg de pollo a Proveedor del Valle",
            estimated_cost_usd=50.0,
            estimated_impact="$50 USD",
        )
        assert result.approved, (
            "Pedido de $50 USD debe auto-aprobarse (bajo umbral)"
        )
        assert "Auto-aprobado" in (result.reason or "")

    def test_high_cost_action_returns_not_approved(self):
        """
        Una acción por encima del umbral debe devolver
        un resultado pendiente de confirmación.
        """
        result = require_confirmation(
            action_type=ActionType.CREATE_PURCHASE_ORDER,
            description="Pedido trimestral a Distribuidora del Valle",
            estimated_cost_usd=2500.0,
            estimated_impact="$2,500 USD",
        )
        assert not result.approved, (
            "Pedido de $2,500 USD no debe auto-aprobarse"
        )
        assert result.reason == "Pendiente de confirmación humana."


class TestFormatConfirmationMessage:
    """Verifica el formateo del mensaje de confirmación."""

    def test_format_message_includes_action_name(self):
        """El mensaje debe incluir el nombre legible de la acción."""
        msg = format_confirmation_message(
            action_type=ActionType.ADJUST_LOYALTY_POINTS,
            description="Ajustar 500 puntos Brasa al cliente ID 1234",
            estimated_impact="500 Brasa Points",
        )
        assert "AJUSTE DE BRASA POINTS" in msg or "Ajuste de Brasa Points" in msg, (
            "El mensaje debe mencionar el tipo de acción"
        )
        assert "500 puntos" in msg or "500 Brasa" in msg

    def test_format_message_includes_description(self):
        """El mensaje debe incluir la descripción de la acción."""
        msg = format_confirmation_message(
            action_type=ActionType.MODIFY_SUPPLIER_STATUS,
            description="Dar de baja a Proveedor X por incumplimiento",
        )
        assert "Dar de baja" in msg

    def test_format_message_includes_impact(self):
        """El mensaje debe incluir el impacto estimado si se proporciona."""
        msg = format_confirmation_message(
            action_type=ActionType.SEND_MARKETING_CAMPAIGN,
            description="Campaña de Navidad",
            estimated_impact="$10,000 USD",
        )
        assert "$10,000" in msg


class TestThresholdConfig:
    """Verifica la configuración de umbrales."""

    def test_default_threshold_is_500(self):
        """El umbral por defecto debe ser $500 USD."""
        assert ThresholdConfig.AUTO_APPROVE_MAX_COST_USD == 500.0

    def test_loyalty_points_always_require_confirmation(self):
        """Ajuste de puntos de lealtad siempre requiere confirmación."""
        assert ThresholdConfig.LOYALTY_POINTS_REQUIRE_CONFIRMATION is True

    def test_supplier_status_change_always_requires_confirmation(self):
        """Cambio de estado de proveedor siempre requiere confirmación."""
        assert ThresholdConfig.SUPPLIER_STATUS_CHANGE_REQUIRES_CONFIRMATION is True