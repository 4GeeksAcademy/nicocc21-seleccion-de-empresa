"""Tests de integración del pipeline de recepción RFP.

Verifica el flujo completo: clasificación, orquestación, workers y síntesis.
NO depende de PostgreSQL — prueba solo la lógica del grafo.
"""

from __future__ import annotations

from data.pipelines.rfp_intake.graph import run_rfp_intake
from data.pipelines.rfp_intake.state import RFPIntakeState


# ─── Nota sobre tests de integración ──────────────────────────────────
# Estos tests verifican la lógica del pipeline SIN base de datos.
# La persistencia real (PostgreSQL) se prueba en los tests de integración
# con la API. Para pruebas offline, ejecutamos nodos manualmente.
# ───────────────────────────────────────────────────────────────────────

RFP_FORMAL = """# Solicitud de Propuesta — Sunset Bay Resorts

Solicitante: Sunset Bay Resorts
Ubicación: Florida, EE.UU.

Tipo de servicio: Concesión co-branded
Alcance: 3 resorts, exclusividad + menú de autor
Volumen: aproximadamente 500 comensales por día por resort
Duración del contrato: 2 años
Presupuesto estimado: 60,000 - 75,000 USD/año
Fecha límite para responder: 15 de diciembre de 2026

Requerimos una propuesta que incluya:
- Marca compartida (co-branding)
- Menú de autor exclusivo que requiere nuevas recetas
- Capacitación del personal local
- Certificación de calidad
"""

RFP_INFORMAL = """Hola Camila,

Tal como hablamos, te escribo para confirmar el interés de Andes Tech Solutions
en contratar el servicio de catering semanal para nuestras oficinas.

Empresa: Andes Tech Solutions
Ubicación: Medellín, Colombia

Necesitamos:
- Catering para 220 empleados
- Servicio semanal (lunes a viernes)
- Menú estándar (sin necesidades especiales)
- Contrato inicial de 12 meses

Por favor confírmame si es viable y un estimado de costo.
"""

DOCUMENTO_INVALIDO = """# Consulta de Franquicia

Hola,

Estamos interesados en abrir una franquicia de Brasaland en nuestra ciudad.
Por favor envíennos información sobre los requisitos y costos de franquicia.

Gracias,
Juan Pérez
"""


class TestRFPIntakeIntegration:
    """Tests de integración del pipeline RFP."""

    def _run_pipeline_offline(self, markdown: str) -> dict:
        """Ejecuta el pipeline offline (sin DB) simulando el grafo."""
        from data.pipelines.rfp_intake.nodes import (
            classifier,
            compute_readability,
            orchestrator,
            synthesizer,
            pdf_to_markdown,
        )

        state = RFPIntakeState(
            ticket_id=1,
            pdf_path="/fake/path.pdf",
            markdown_content=markdown,
        )

        state = compute_readability(state)
        state = classifier(state)

        if not state.is_valid:
            return {
                "success": True,
                "ticket_id": 1,
                "status": "descartado",
                "summary": None,
            }

        state = orchestrator(state)

        # Workers
        dept_functions = {
            "marketing": __import__("data.pipelines.rfp_intake.nodes", fromlist=["worker_marketing"]).worker_marketing,
            "operaciones": __import__("data.pipelines.rfp_intake.nodes", fromlist=["worker_operaciones"]).worker_operaciones,
            "procurement": __import__("data.pipelines.rfp_intake.nodes", fromlist=["worker_procurement"]).worker_procurement,
            "training": __import__("data.pipelines.rfp_intake.nodes", fromlist=["worker_training"]).worker_training,
        }

        if state.rfp_metadata:
            for dept_id in state.rfp_metadata.departments_needed:
                if dept_id in dept_functions:
                    state = dept_functions[dept_id](state)

        state = synthesizer(state)

        return {
            "success": True,
            "ticket_id": 1,
            "status": "analisis_completo",
            "summary": state.final_summary,
            "departments_analyzed": [a.department_id for a in state.department_analyses],
            "readability": {
                "flesch_reading_ease": state.readability.flesch_reading_ease if state.readability else None,
                "word_count": state.readability.word_count if state.readability else None,
            } if state.readability else None,
        }

    def test_flujo_completo_rfp_formal(self):
        """RFP formal: debe activar los 4 departamentos y producir resumen."""
        result = self._run_pipeline_offline(RFP_FORMAL)
        assert result["status"] == "analisis_completo"
        assert result["summary"] is not None
        assert "marketing" in result["departments_analyzed"]
        assert "operaciones" in result["departments_analyzed"]
        assert "procurement" in result["departments_analyzed"]
        assert "training" in result["departments_analyzed"]
        assert result["readability"] is not None

    def test_flujo_completo_rfp_informal(self):
        """RFP informal: debe activar los departamentos relevantes."""
        result = self._run_pipeline_offline(RFP_INFORMAL)
        assert result["status"] == "analisis_completo"
        assert result["summary"] is not None
        assert "marketing" in result["departments_analyzed"]
        # Catering con menú estándar → training no necesariamente se activa
        # pero operaciones y procurement sí deberían
        assert "procurement" in result["departments_analyzed"]

    def test_flujo_completo_documento_invalido(self):
        """Documento inválido: debe descartarse sin resumen."""
        result = self._run_pipeline_offline(DOCUMENTO_INVALIDO)
        assert result["status"] == "descartado"
        assert result["summary"] is None