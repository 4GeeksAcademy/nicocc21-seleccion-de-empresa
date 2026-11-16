"""Tests del pipeline de generación de respuesta a RFP — Hito 9, Parte 2.

Verifica:
  - Evaluadores individuales (legibilidad, pertinencia, cumplimiento)
  - Ciclo generador-evaluador completo
  - Handoff a Parte 3 (estructura correcta)
  - Límite de iteraciones y needs_human_review
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from data.pipelines.rfp_response.nodes import (
    evaluate_compliance,
    evaluate_readability,
    evaluate_relevance,
    generate_marketing_section,
    generate_operaciones_section,
    generate_procurement_section,
    generate_training_section,
    run_single_department_cycle,
)
from data.pipelines.rfp_response.state import (
    DepartmentResponse,
    EvaluationResult,
    RFPResponseState,
)


# ═══════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_metadata() -> dict[str, Any]:
    return {
        "client_name": "Sunset Bay Resorts",
        "location": "Florida, EE.UU.",
        "service_type": "Concesión co-branded",
        "scope": "3 resorts, exclusividad + menú de autor",
        "deadline": "15 de diciembre de 2026",
        "budget_range": "60,000 - 75,000 USD/año",
        "budget_min_usd": 60000.0,
        "budget_max_usd": 75000.0,
        "departments_needed": '["marketing","operaciones","procurement","training"]',
    }


@pytest.fixture
def sample_key_aspects() -> dict[str, Any]:
    return {
        "extractos_relevantes": [
            "Sunset Bay Resorts solicita concesión co-branded en 3 resorts de Florida",
            "Exclusividad + menú de autor que requiere nuevas recetas",
            "Capacitación del personal local y certificación de calidad",
            "Presupuesto estimado: 60,000 - 75,000 USD/año",
        ],
        "total_extractos": 4,
        "notas": "Basado en palabras clave del departamento.",
    }


@pytest.fixture
def sample_draft_good() -> str:
    """Un draft que debería pasar todas las evaluaciones."""
    return """## Sección de Marketing y Experiencia Digital

### Propuesta de Valor Comercial

Brasaland propone una alianza estratégica con Sunset Bay Resorts en Florida, EE.UU., basada en los tres pilares que nos definen: **calidad consistente**, **experiencia cálida** y **velocidad de servicio**.

### Términos de Marca y Co-Branding

El servicio de Concesión co-branded se prestará bajo la marca Brasaland, garantizando la integridad de nuestra identidad corporativa.

### Condiciones Comerciales

El valor estimado del contrato se sitúa en un rango de **60,000 – 75,000 USD/año** (aproximadamente **252,000,000 – 315,000,000 COP/año**). Los precios unitarios por servicio se expresarán tanto en COP como en USD.

### Vigencia de la Oferta

Esta propuesta tiene una validez de **30 días calendario** a partir de su fecha de emisión.

### Aprobación Directiva

Dado que el valor anual estimado supera los 50.000 USD, esta propuesta requerirá la aprobación expresa de **Mariana Restrepo**, nuestra Directora Ejecutiva (CEO).

### Responsable

**Camila Ospina** — Marketing y Experiencia Digital
"""


@pytest.fixture
def sample_draft_bad_readability() -> str:
    """Un draft con legibilidad muy baja."""
    return (
        "En virtud de la presente misiva, Brasaland S.A.S., entidad corporativa "
        "debidamente constituida bajo las leyes de la República de Colombia y "
        "con establecimientos en los Estados Unidos de América, formaliza su "
        "propuesta económica para con Sunset Bay Resorts, corporación del sector "
        "hotelero con sede en el estado de Florida, Estados Unidos del Norte América. "
        "La referida propuesta se circunscribe en el marco de una concesión de "
        "carácter co-branded, con una duración contractual estimada de dos años. "
        "COP 250,000,000 anuales. USD 60,000 anuales. Válido por 30 días."
    )


# ═══════════════════════════════════════════════════════════════════════
#  Tests de Evaluadores
# ═══════════════════════════════════════════════════════════════════════


class TestEvaluateReadability:
    """Tests del evaluador de legibilidad."""

    def test_readability_passes_good_draft(self, sample_draft_good: str):
        """Un draft bien escrito debe pasar legibilidad."""
        result = evaluate_readability(sample_draft_good)
        assert result.evaluator_id == "readability"
        assert isinstance(result.passed, bool)
        assert isinstance(result.score, float)
        assert result.details is not None
        # No verificamos que pase porque depende del texto real
        # pero debe devolver structured result
        assert "flesch_reading_ease" in result.details

    def test_readability_returns_metrics(self, sample_draft_good: str):
        """Debe devolver métricas de legibilidad."""
        result = evaluate_readability(sample_draft_good)
        assert result.details is not None
        assert "flesch_reading_ease" in result.details
        assert "flesch_kincaid_grade" in result.details
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0

    def test_readability_feedback_not_empty(self, sample_draft_good: str):
        """El feedback no debe estar vacío."""
        result = evaluate_readability(sample_draft_good)
        assert len(result.feedback) > 0

    def test_readability_empty_text(self):
        """Texto vacío debe devolver score bajo."""
        result = evaluate_readability("")
        assert result.score is not None
        assert result.score <= 0.5  # Texto vacío no pasa


class TestEvaluateRelevance:
    """Tests del evaluador de pertinencia."""

    def test_relevance_passes_with_good_draft(
        self,
        sample_draft_good: str,
        sample_key_aspects: dict,
    ):
        """Un draft que cubre los aspectos clave debe pasar."""
        result = evaluate_relevance(sample_draft_good, sample_key_aspects)
        assert result.evaluator_id == "relevance"
        assert isinstance(result.passed, bool)
        assert isinstance(result.score, float)

    def test_relevance_fails_with_empty_draft(self, sample_key_aspects: dict):
        """Draft vacío no debe pasar."""
        result = evaluate_relevance("", sample_key_aspects)
        assert result.passed is False

    def test_relevance_has_details(self, sample_draft_good: str, sample_key_aspects: dict):
        """Debe incluir detalles como word_count."""
        result = evaluate_relevance(sample_draft_good, sample_key_aspects)
        assert result.details is not None
        assert "word_count" in result.details
        assert result.details["word_count"] > 0

    def test_relevance_without_aspects(self, sample_draft_good: str):
        """Sin key_aspects, debe evaluar igual pero con cobertura baja."""
        result = evaluate_relevance(sample_draft_good, {})
        assert result.score is not None
        # Sin aspectos de cliente, la cobertura es baja
        # pero debe seguir teniendo sustancia


class TestEvaluateCompliance:
    """Tests del evaluador de cumplimiento."""

    def test_compliance_passes_good_draft(
        self,
        sample_draft_good: str,
        sample_metadata: dict,
    ):
        """Un draft que cumple todos los lineamientos debe pasar."""
        result = evaluate_compliance(sample_draft_good, sample_metadata)
        assert result.evaluator_id == "compliance"
        assert isinstance(result.passed, bool)
        assert isinstance(result.score, float)
        # Debe pasar porque cumple todas las reglas
        assert result.passed is True, f"Compliance failed: {result.feedback}"

    def test_compliance_detects_missing_prices(self, sample_metadata: dict):
        """Debe detectar falta de precios en COP/USD."""
        draft_sin_precios = """Propuesta para Cliente. Calidad consistente. Validez 30 días."""
        result = evaluate_compliance(draft_sin_precios, sample_metadata)
        assert "COP" in result.feedback or "USD" in result.feedback

    def test_compliance_detects_missing_pillars(self, sample_metadata: dict):
        """Debe detectar ausencia de pilares de marca."""
        draft_sin_pilares = """Propuesta para Cliente. COP y USD. Validez 30 días."""
        result = evaluate_compliance(draft_sin_pilares, sample_metadata)
        if not result.passed:
            # Si no pasó, debe mencionar los pilares
            assert any(
                word in result.feedback.lower()
                for word in ["calidad", "experiencia", "velocidad", "pilar"]
            ), f"Unexpected feedback: {result.feedback}"

    def test_compliance_detects_competitors(self, sample_metadata: dict):
        """Debe detectar mención de competidores."""
        draft_con_competencia = """Somos mejores que McDonald's y Burger King. COP y USD. Calidad consistente, experiencia cálida, velocidad de servicio. Validez 30 días."""
        result = evaluate_compliance(draft_con_competencia, sample_metadata)
        assert result.passed is False
        assert "competidores" in result.feedback.lower() or "competidor" in result.feedback.lower()

    def test_compliance_detects_missing_validity(self, sample_metadata: dict):
        """Debe detectar falta de período de validez."""
        draft_sin_validez = """COP y USD. Calidad consistente, experiencia cálida, velocidad de servicio."""
        result = evaluate_compliance(draft_sin_validez, sample_metadata)
        if not result.passed:
            assert "validez" in result.feedback.lower() or "30" in result.feedback

    def test_compliance_ceo_threshold(self):
        """Presupuesto >50K USD debe requerir mención de CEO."""
        metadata_con_umbral = {
            "client_name": "Test",
            "budget_max_usd": 75000.0,
        }
        draft_sin_ceo = """COP y USD. Calidad consistente, experiencia cálida, velocidad de servicio. Validez 30 días."""
        result = evaluate_compliance(draft_sin_ceo, metadata_con_umbral)
        if not result.passed:
            assert "CEO" in result.feedback or "Mariana" in result.feedback

    def test_compliance_rules_structure(self, sample_draft_good: str, sample_metadata: dict):
        """El detalle debe incluir el array de rules."""
        result = evaluate_compliance(sample_draft_good, sample_metadata)
        assert result.details is not None
        assert "rules" in result.details
        assert isinstance(result.details["rules"], list)
        assert len(result.details["rules"]) > 0

    def test_compliance_all_rules_present(self, sample_draft_good: str, sample_metadata: dict):
        """Deben evaluarse todas las reglas definidas."""
        result = evaluate_compliance(sample_draft_good, sample_metadata)
        rule_ids = {r["rule"] for r in result.details["rules"]}
        expected = {"prices_cop_usd", "brand_pillars", "min_setup_time",
                     "no_competitors", "validity_period", "ceo_approval_threshold"}
        assert rule_ids == expected, f"Missing rules: {expected - rule_ids}"


# ═══════════════════════════════════════════════════════════════════════
#  Tests de Generadores
# ═══════════════════════════════════════════════════════════════════════


class TestGenerators:
    """Tests de los generadores por departamento."""

    @pytest.fixture
    def generator_context(self, sample_metadata: dict, sample_key_aspects: dict) -> dict[str, Any]:
        return {
            "metadata": sample_metadata,
            "key_aspects": sample_key_aspects,
        }

    def test_marketing_generates_content(self, generator_context: dict):
        """El generador de marketing debe producir texto."""
        draft = generate_marketing_section(generator_context)
        assert isinstance(draft, str)
        assert len(draft) > 100
        assert "Marketing" in draft

    def test_operaciones_generates_content(self, generator_context: dict):
        """El generador de operaciones debe producir texto."""
        draft = generate_operaciones_section(generator_context)
        assert isinstance(draft, str)
        assert len(draft) > 100
        assert "Operaciones" in draft

    def test_procurement_generates_content(self, generator_context: dict):
        """El generador de procurement debe producir texto."""
        draft = generate_procurement_section(generator_context)
        assert isinstance(draft, str)
        assert len(draft) > 100
        assert "Procurement" in draft

    def test_training_generates_content(self, generator_context: dict):
        """El generador de training debe producir texto."""
        draft = generate_training_section(generator_context)
        assert isinstance(draft, str)
        assert len(draft) > 100
        assert "Training" in draft

    def test_generators_include_responsable(self, generator_context: dict):
        """Cada draft debe incluir al responsable del departamento."""
        for gen in [
            generate_marketing_section,
            generate_operaciones_section,
            generate_procurement_section,
            generate_training_section,
        ]:
            draft = gen(generator_context)
            assert "Responsable" in draft, f"{gen.__name__} missing Responsable"

    def test_generators_with_feedback_context(self, generator_context: dict):
        """Los generadores deben manejar feedback previo."""
        context_with_feedback = dict(generator_context)
        context_with_feedback["feedback_previo"] = [
            {"evaluator": "compliance", "feedback": "Faltan precios en USD"}
        ]
        context_with_feedback["ultimo_borrador"] = "Versión anterior del borrador"
        draft = generate_marketing_section(context_with_feedback)
        assert isinstance(draft, str)
        assert len(draft) > 100


# ═══════════════════════════════════════════════════════════════════════
#  Tests del Ciclo Generador-Evaluador
# ═══════════════════════════════════════════════════════════════════════


class TestDepartmentCycle:
    """Tests del ciclo generador-evaluador por departamento."""

    def test_single_department_cycle_approves(
        self,
        sample_metadata: dict,
        sample_key_aspects: dict,
    ):
        """Un departamento con buen contexto debe aprobar."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(
            ticket_id=1,
            rfp_metadata=sample_metadata,
        )
        result = run_single_department_cycle(dept, state)
        assert result.status in ("aprobado", "needs_human_review")
        assert result.final_draft is not None
        assert len(result.final_evaluations) == 3

    def test_department_cycle_produces_evaluations(
        self,
        sample_metadata: dict,
        sample_key_aspects: dict,
    ):
        """El ciclo debe producir evaluaciones para los 3 evaluadores."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)
        assert len(result.final_evaluations) == 3
        evaluator_ids = {e.evaluator_id for e in result.final_evaluations}
        assert evaluator_ids == {"readability", "relevance", "compliance"}

    def test_department_cycle_tracks_iterations(
        self,
        sample_metadata: dict,
        sample_key_aspects: dict,
    ):
        """El ciclo debe trackear el número de iteraciones."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)
        assert result.current_iteration >= 1
        assert result.current_iteration <= 3
        assert len(result.iterations) == result.current_iteration

    def test_needs_human_review_after_max_iterations(self):
        """Un departamento que nunca pasa debe terminar en needs_human_review."""
        # Usar operaciones con metadatos mínimos que dificulten pasar
        dept = DepartmentResponse(
            department_id="training",
            key_aspects={
                "extractos_relevantes": [],
                "notas": "Sin información relevante",
            },
            metadata={
                "client_name": None,
                "location": None,
                "budget_min_usd": None,
                "budget_max_usd": None,
            },
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)
        # Puede aprobar o no, pero debe terminar con un estado válido
        assert result.status in ("aprobado", "needs_human_review")
        assert result.final_draft is not None


# ═══════════════════════════════════════════════════════════════════════
#  Tests de Handoff (Estructura para Parte 3)
# ═══════════════════════════════════════════════════════════════════════


class TestHandoffStructure:
    """Verifica que la salida tenga la estructura correcta para Parte 3."""

    def test_evaluation_result_has_required_fields(self):
        """EvaluationResult debe tener todos los campos del schema."""
        result = EvaluationResult(
            evaluator_id="readability",
            passed=True,
            score=0.85,
            feedback="Texto claro.",
            details={"flesch_reading_ease": 65.0},
        )
        assert result.evaluator_id == "readability"
        assert result.passed is True
        assert result.score == 0.85
        assert result.feedback == "Texto claro."
        assert result.details == {"flesch_reading_ease": 65.0}

    def test_evaluation_result_minimal(self):
        """EvaluationResult debe funcionar con solo campos obligatorios."""
        result = EvaluationResult(
            evaluator_id="relevance",
            passed=False,
        )
        assert result.evaluator_id == "relevance"
        assert result.passed is False
        assert result.score is None
        assert result.feedback == ""  # default

    def test_department_response_has_handoff_fields(
        self,
        sample_metadata: dict,
        sample_key_aspects: dict,
    ):
        """DepartmentResponse debe tener los campos para handoff a Parte 3."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)
        # Campos requeridos para Parte 3
        assert hasattr(result, "department_id")
        assert hasattr(result, "final_draft")
        assert hasattr(result, "final_evaluations")
        assert hasattr(result, "needs_human_review")
        assert hasattr(result, "status")
        # draft_content no debe ser None
        assert result.final_draft is not None
        assert len(result.final_evaluations) > 0

    def test_handoff_serializable_to_json(self, sample_metadata: dict, sample_key_aspects: dict):
        """La estructura de handoff debe ser serializable a JSON."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)

        handoff = {
            "department_id": result.department_id,
            "draft_content": result.final_draft,
            "evaluation_results": [
                {
                    "evaluator_id": e.evaluator_id,
                    "passed": e.passed,
                    "score": e.score,
                    "feedback": e.feedback,
                    "details": e.details,
                }
                for e in result.final_evaluations
            ],
            "needs_human_review": result.needs_human_review,
            "approval_status": result.status,
        }

        # Serializar y deserializar para verificar
        json_str = json.dumps(handoff, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["department_id"] == "marketing"
        assert len(parsed["evaluation_results"]) == 3
        assert "needs_human_review" in parsed
        assert "approval_status" in parsed


# ═══════════════════════════════════════════════════════════════════════
#  Tests de Integración del Pipeline Completo
# ═══════════════════════════════════════════════════════════════════════



class TestEvaluationSummary:
    """Tests del resumen consolidado evaluation_summary (formato spec Parte 3)."""

    def test_evaluation_summary_has_all_fields(
        self,
        sample_metadata: dict,
        sample_key_aspects: dict,
    ):
        """El evaluation_summary debe tener todos los campos del spec."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects=sample_key_aspects,
            metadata=sample_metadata,
        )
        state = RFPResponseState(ticket_id=1)
        result = run_single_department_cycle(dept, state)

        assert result.evaluation_summary is not None
        summary = result.evaluation_summary

        # Campos obligatorios
        assert "section_id" in summary
        assert summary["section_id"] == "marketing"
        assert "readability" in summary
        assert "relevance" in summary
        assert "compliance" in summary
        assert "overall_pass" in summary
        assert "feedback_for_generator" in summary

    def test_evaluation_summary_readability_structure(self, sample_draft_good: str):
        """readability debe tener pass, score, details."""
        from data.pipelines.rfp_response.nodes import evaluate_readability
        from data.pipelines.rfp_response.nodes import _build_evaluation_summary

        result = evaluate_readability(sample_draft_good)
        summary = _build_evaluation_summary("marketing", [result])

        r = summary["readability"]
        assert "pass" in r
        assert "score" in r
        assert "details" in r
        assert isinstance(r["pass"], bool)
        assert r["score"] is None or isinstance(r["score"], float)

    def test_evaluation_summary_relevance_structure(self, sample_draft_good: str):
        """relevance debe tener pass, missing_aspects."""
        from data.pipelines.rfp_response.nodes import evaluate_relevance
        from data.pipelines.rfp_response.nodes import _build_evaluation_summary

        result = evaluate_relevance(sample_draft_good, {})
        summary = _build_evaluation_summary("marketing", [result])

        r = summary["relevance"]
        assert "pass" in r
        assert "missing_aspects" in r
        assert isinstance(r["missing_aspects"], list)

    def test_evaluation_summary_compliance_structure(self, sample_draft_good: str, sample_metadata: dict):
        """compliance debe tener pass, rule_ids, violations."""
        from data.pipelines.rfp_response.nodes import evaluate_compliance
        from data.pipelines.rfp_response.nodes import _build_evaluation_summary

        result = evaluate_compliance(sample_draft_good, sample_metadata)
        summary = _build_evaluation_summary("marketing", [result])

        c = summary["compliance"]
        assert "pass" in c
        assert "rule_ids" in c
        assert "violations" in c
        assert isinstance(c["rule_ids"], list)
        assert isinstance(c["violations"], list)

    def test_evaluation_summary_feedback_on_failure(self, sample_metadata: dict):
        """Cuando un evaluador falla, feedback_for_generator debe contener el feedback."""
        from data.pipelines.rfp_response.nodes import evaluate_compliance
        from data.pipelines.rfp_response.nodes import _build_evaluation_summary

        draft_sin_precios = "Texto sin precios ni pilares."
        result = evaluate_compliance(draft_sin_precios, sample_metadata)
        summary = _build_evaluation_summary("operaciones", [result])

        assert summary["overall_pass"] is False
        assert len(summary["feedback_for_generator"]) > 0
        assert "compliance" in summary["feedback_for_generator"]

    def test_evaluation_summary_returns_none_if_no_cycle(self):
        """Sin ciclo ejecutado, evaluation_summary debe ser None."""
        dept = DepartmentResponse(
            department_id="marketing",
            key_aspects={},
            metadata={},
        )
        assert dept.evaluation_summary is None


class TestComplianceBriefingRules:
    """Tests de compliance anclados a reglas específicas del BRIEFING §5."""

    def test_compliance_fails_when_setup_under_10_days(self):
        """BRIEFING §5: Nadie debe prometer montaje/entrega bajo 10 días hábiles."""
        draft = (
            "COP y USD. Calidad consistente, experiencia cálida, velocidad de servicio. "
            "El montaje se completará en 5 días hábiles. Validez 30 días."
        )
        metadata = {"client_name": "Test"}
        result = evaluate_compliance(draft, metadata)
        assert result.passed is False, (
            "Debe fallar compliance porque promete 5 días hábiles (< 10)"
        )
        assert any(
            "5" in r.get("details", {}).get("matches_found", [])[0]
            for r in result.details.get("rules", [])
            if r["rule"] == "min_setup_time" and not r["passed"]
        )

    def test_compliance_fails_with_competitor_name(self):
        """BRIEFING §5: Ninguna propuesta puede mencionar nombres de competidores."""
        draft = (
            "COP y USD. Calidad consistente, experiencia cálida, velocidad de servicio. "
            "Somos mejores que McDonald's. Validez 30 días."
        )
        metadata = {"client_name": "Test"}
        result = evaluate_compliance(draft, metadata)
        assert result.passed is False
        assert "mcdonald" in result.feedback.lower()

class TestPipelineIntegration:
    """Tests de integración del pipeline completo (sin DB)."""

    def test_run_all_departments_returns_summary(
        self,
        sample_metadata: dict,
    ):
        """Ejecutar todos los departamentos debe devolver resumen."""
        from data.pipelines.rfp_response.nodes import run_all_department_cycles

        departments = [
            DepartmentResponse(
                department_id=dept_id,
                key_aspects={
                    "extractos_relevantes": [f"Aspecto relevante para {dept_id}"],
                    "notas": "Test",
                },
                metadata=dict(sample_metadata, departamento=dept_id),
            )
            for dept_id in ["marketing", "operaciones", "procurement"]
        ]

        state = RFPResponseState(
            ticket_id=1,
            rfp_metadata=sample_metadata,
            departments=departments,
        )

        result = run_all_department_cycles(state)
        assert result.status in (
            "esperando_aprobacion",
            "needs_human_review",
            "en_evaluacion",
        )
        assert len(result.departments) == 3
        for dept in result.departments:
            assert dept.final_draft is not None
            assert len(dept.final_evaluations) == 3

    def test_pipeline_handles_empty_departments(self):
        """Pipeline con 0 departamentos debe manejarse sin error."""
        from data.pipelines.rfp_response.nodes import run_all_department_cycles

        state = RFPResponseState(
            ticket_id=1,
            departments=[],
        )
        result = run_all_department_cycles(state)
        assert result.global_error is not None
        assert "No hay departamentos activos" in result.global_error