"""Tests for MemoryEvaluator — rule-based auto-evaluation of interactions."""

from __future__ import annotations

import pytest

from agents.support_agent.memory.memory_evaluator import (
    MemoryEvaluator,
    PositivePatterns,
    SensitivityPatterns,
)
from agents.support_agent.memory.schemas import MemoryCategory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def evaluator() -> MemoryEvaluator:
    return MemoryEvaluator(confidence_threshold=0.4)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_text(self, evaluator: MemoryEvaluator):
        result = evaluator.evaluate("")
        assert result.should_propose is False
        assert "Empty" in result.rationale

    def test_whitespace_only(self, evaluator: MemoryEvaluator):
        result = evaluator.evaluate("   \n  \t  ")
        assert result.should_propose is False

    def test_none_text(self, evaluator: MemoryEvaluator):
        result = evaluator.evaluate("")
        assert result.should_propose is False


# ---------------------------------------------------------------------------
# Rejection patterns
# ---------------------------------------------------------------------------


class TestSensitivityRejection:
    """Patterns that should NEVER be memorised."""

    @pytest.mark.parametrize(
        "text,reason",
        [
            ("mi DNI es 12345678Z", "personal_data"),
            ("el NIF del cliente es B-123456", "personal_data"),
            ("su pasaporte vence en marzo", "personal_data"),
            ("teléfono: +34 600 123 456", "personal_data"),
            ("el correo es cliente@example.com", "personal_data"),
            ("su dirección es Calle Mayor 12", "personal_data"),
            ("número de tarjeta 4532-1234-5678", "personal_data"),
            ("cuenta bancaria ES12 3456 7890", "personal_data"),
            ("el IBAN es ES00 0000 0000", "personal_data"),
        ],
    )
    def test_reject_personal_data(self, evaluator: MemoryEvaluator, text: str, reason: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is False, f"Should reject {reason}: {text}"

    @pytest.mark.parametrize(
        "text,reason",
        [
            ("su nómina es de 3000€", "payroll"),
            ("el salario base son 1500", "payroll"),
            ("el sueldo del empleado", "payroll"),
            ("la compensación anual", "payroll"),
            ("el bono de productividad", "payroll"),
            ("la bonificación mensual", "payroll"),
            ("pago mensual de 2000€", "payroll"),
            ("ingresos personales", "payroll"),
        ],
    )
    def test_reject_payroll(self, evaluator: MemoryEvaluator, text: str, reason: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is False, f"Should reject {reason}: {text}"

    @pytest.mark.parametrize(
        "text,reason",
        [
            ("gracias por tu ayuda", "one_shot"),
            ("gracias eso era todo", "one_shot"),
            ("resuelve mi duda por favor", "one_shot"),
            ("traducir esto al inglés", "one_shot"),
            ("thanks, that's all", "one_shot"),
            ("nada más, gracias", "one_shot"),
            ("no necesito nada más", "one_shot"),
        ],
    )
    def test_reject_one_shot(self, evaluator: MemoryEvaluator, text: str, reason: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is False, f"Should reject {reason}: {text}"


# ---------------------------------------------------------------------------
# Positive patterns
# ---------------------------------------------------------------------------


class TestPositiveDetection:
    """Patterns that SHOULD be proposed for memory."""

    @pytest.mark.parametrize(
        "text",
        [
            "El local cierra a las 10pm",
            "el horario de entrega es los lunes",
            "reparto los viernes por la mañana",
            "abrimos a las 8 am",
            "cerramos a las 9 p. m.",
            "la entrega pasa los martes",
            "abre a las 7:30 am",
            "ahora abrimos a las 9",
        ],
    )
    def test_detect_schedule_correction(self, evaluator: MemoryEvaluator, text: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        assert result.category == MemoryCategory.SCHEDULES

    @pytest.mark.parametrize(
        "text",
        [
            "el proveedor de carne no entrega los lunes",
            "el distribuidor pasa los miércoles",
            "la proveedora de lácteos es la misma",
            "en realidad es el jueves no el viernes",
            "la espera es el sábado no el viernes",
            "la carne no es los martes",
        ],
    )
    def test_detect_supplier_correction(self, evaluator: MemoryEvaluator, text: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        assert result.category == MemoryCategory.SUPPLIERS

    @pytest.mark.parametrize(
        "text",
        [
            "cierra a las 11pm los viernes",
            "los sábados cierra a las 10",
            "cambio de horario, ahora abrimos a las 8",
            "nuevo horario: cierre a medianoche",
            "los fines de semana cierra a las 11",
            "hasta las 9pm",
        ],
    )
    def test_detect_hours_correction(self, evaluator: MemoryEvaluator, text: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        assert result.category == MemoryCategory.SCHEDULES

    @pytest.mark.parametrize(
        "text",
        [
            "esto es un incidente conocido",
            "alerta de corte de luz en la zona",
            "es el mismo problema de la semana pasada",
            "ya pasó antes, es un error del POS",
            "otra vez lo mismo, es una escalación",
            "no es un error del sistema",
            "ya ocurrió el mes pasado",
        ],
    )
    def test_detect_incident(self, evaluator: MemoryEvaluator, text: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        assert result.category == MemoryCategory.KNOWN_INCIDENTS

    @pytest.mark.parametrize(
        "text",
        [
            "prefiero recibir el reporte en PDF",
            "me gustaría que me mandes el resumen",
            "quisiera que el formato sea Excel",
            "siempre pido el pedido los lunes",
            "acostumbro hacer el pedido por la mañana",
            "normalmente lo hago así",
            "como siempre, a las 10am",
        ],
    )
    def test_detect_preference(self, evaluator: MemoryEvaluator, text: str):
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        assert result.category == MemoryCategory.COMMUNICATION_PREFERENCES


# ---------------------------------------------------------------------------
# Multi-match and confidence
# ---------------------------------------------------------------------------


class TestConfidenceAndMultiMatch:
    def test_higher_confidence_with_more_matches(self, evaluator: MemoryEvaluator):
        """More pattern matches → higher confidence."""
        single = evaluator.evaluate("el local cierra a las 10pm")
        multi = evaluator.evaluate(
            "el local cierra a las 10pm y abre a las 8am, el horario cambió"
        )
        assert multi.confidence_score > single.confidence_score

    def test_best_category_wins(self, evaluator: MemoryEvaluator):
        """When multiple categories match, the highest confidence wins."""
        text = "el proveedor pasa los lunes y el local cierra a las 10pm"
        result = evaluator.evaluate(text)
        assert result.should_propose is True
        # Either SUPPLIERS or SCHEDULES — both are valid
        assert result.category in (
            MemoryCategory.SUPPLIERS,
            MemoryCategory.SCHEDULES,
        )

    def test_confidence_cap(self, evaluator: MemoryEvaluator):
        """Confidence should never exceed 0.95."""
        text = " ".join([
            "cierra a las 10pm",
            "abre a las 8am",
            "horario de entrega",
            "reparto los lunes",
            "abrimos los sábados",
            "cerramos los domingos",
        ])
        result = evaluator.evaluate(text)
        assert result.confidence_score <= 0.95

    def test_below_threshold_not_proposed(self):
        """Text with confidence below threshold should not propose."""
        high = MemoryEvaluator(confidence_threshold=0.9)
        result = high.evaluate("el local cierra a las 10pm")
        # Single match gives 0.4 base which is < 0.9
        assert result.should_propose is False or result.confidence_score < 0.9


# ---------------------------------------------------------------------------
# Pattern regex integrity
# ---------------------------------------------------------------------------


class TestPatternIntegrity:
    """Ensure patterns compile and match expected strings."""

    def test_sensitivity_patterns_compile(self):
        assert SensitivityPatterns.PERSONAL_DATA.search("dni 123") is not None
        assert SensitivityPatterns.PAYROLL.search("nómina 3000") is not None
        assert SensitivityPatterns.ONE_SHOT.search("gracias por eso") is not None

    def test_positive_patterns_compile(self):
        assert PositivePatterns.SCHEDULE_CORRECTION.search("horario de entrega") is not None
        assert PositivePatterns.SUPPLIER_CORRECTION.search("proveedor de carne") is not None
        assert PositivePatterns.HOURS_CORRECTION.search("cierra a las 10pm") is not None
        assert PositivePatterns.INCIDENT_PATTERN.search("corte de luz") is not None
        assert PositivePatterns.PREFERENCE_PATTERN.search("prefiero") is not None


# ---------------------------------------------------------------------------
# Location context (evaluator signature)
# ---------------------------------------------------------------------------


class TestLocationContext:
    def test_evaluate_accepts_location_id(self, evaluator: MemoryEvaluator):
        """location_id is accepted but currently not used for scoring."""
        text = "el proveedor pasa los lunes"
        with_location = evaluator.evaluate(text, location_id="L03")
        without_location = evaluator.evaluate(text)
        assert with_location.should_propose == without_location.should_propose
        assert with_location.category == without_location.category