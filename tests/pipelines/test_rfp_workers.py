"""Tests unitarios de los workers departamentales del pipeline RFP.

Verifica que cada worker extraiga aspectos clave según las palabras clave
de su departamento, sin inventar cifras.
"""

from __future__ import annotations

from data.pipelines.rfp_intake.nodes import (
    orchestrator,
    worker_marketing,
    worker_operaciones,
    worker_procurement,
    worker_training,
)
from data.pipelines.rfp_intake.state import RFPIntakeState


RFP_COMPLETA = """# Solicitud de Propuesta — Sunset Bay Resorts

Solicitante: Sunset Bay Resorts
Ubicación: Florida, EE.UU.

Tipo de servicio: Concesión co-branded
Alcance: 3 resorts, exclusividad + menú de autor
Volumen: aproximadamente 500 comensales por día por resort
Duración del contrato: 2 años
Presupuesto estimado: 60,000 - 75,000 USD/año
Fecha límite para responder: 15 de diciembre de 2026

Requerimos una propuesta que incluya:
- Marca compartida (co-branding) con términos de marca definidos
- Exclusividad para la operación en los 3 resorts
- Menú de autor exclusivo que requiere desarrollo de nuevas recetas
- Capacitación del personal local en los nuevos estándares
- Certificación de calidad para la operación
- Costo operativo por evento
- Suministro de insumos desde proveedores locales
"""


def _make_processed_state() -> RFPIntakeState:
    """Crea un state ya clasificado y orquestado para probar workers."""
    state = RFPIntakeState(
        ticket_id=1,
        pdf_path="/fake/path.pdf",
        markdown_content=RFP_COMPLETA,
        is_valid=True,
    )
    state = orchestrator(state)
    return state


class TestRFPWorkers:
    """Suite de tests para los workers departamentales."""

    def test_worker_marketing_extrae_aspectos(self):
        """El worker de marketing debe extraer aspectos de marca."""
        state = _make_processed_state()
        result = worker_marketing(state)
        assert len(result.department_analyses) > 0
        marketing = [a for a in result.department_analyses if a.department_id == "marketing"]
        assert len(marketing) == 1
        aspects = marketing[0].key_aspects
        assert "extractos_relevantes" in aspects
        assert len(aspects["extractos_relevantes"]) > 0
        # Debe haber encontrado algo de co-branding o marca
        all_text = " ".join(aspects["extractos_relevantes"]).lower()
        assert any(kw in all_text for kw in ["marca", "co-branding", "exclusividad"])

    def test_worker_operaciones_extrae_aspectos(self):
        """El worker de operaciones debe extraer aspectos operativos."""
        state = _make_processed_state()
        result = worker_operaciones(state)
        operaciones = [a for a in result.department_analyses if a.department_id == "operaciones"]
        assert len(operaciones) == 1
        aspects = operaciones[0].key_aspects
        assert "extractos_relevantes" in aspects
        assert len(aspects["extractos_relevantes"]) > 0

    def test_worker_procurement_extrae_aspectos(self):
        """El worker de procurement debe extraer aspectos de insumos/proveedores."""
        state = _make_processed_state()
        result = worker_procurement(state)
        procurement = [a for a in result.department_analyses if a.department_id == "procurement"]
        assert len(procurement) == 1
        aspects = procurement[0].key_aspects
        assert "extractos_relevantes" in aspects

    def test_worker_training_extrae_aspectos(self):
        """El worker de training debe extraer aspectos de certificación/recetas."""
        state = _make_processed_state()
        result = worker_training(state)
        training = [a for a in result.department_analyses if a.department_id == "training"]
        assert len(training) == 1
        aspects = training[0].key_aspects
        assert "extractos_relevantes" in aspects
        all_text = " ".join(aspects["extractos_relevantes"]).lower()
        assert any(kw in all_text for kw in ["receta", "certificación", "certificacion", "estándar", "estandar"])

    def test_worker_no_inventa_cifras(self):
        """Los workers no deben inventar cifras que no están en el texto."""
        state = _make_processed_state()
        result = worker_marketing(state)
        marketing = [a for a in result.department_analyses if a.department_id == "marketing"][0]
        aspects = marketing.key_aspects
        # key_aspects no debe contener números que no aparecen en el original
        original_text = RFP_COMPLETA.lower()
        for extract in aspects.get("extractos_relevantes", []):
            # Buscar números en el extracto
            import re
            numbers = re.findall(r'\d+', extract)
            for num in numbers:
                # Verificar que ese número o contexto similar está en el original
                assert num in original_text, f"El número {num} no aparece en el documento original"