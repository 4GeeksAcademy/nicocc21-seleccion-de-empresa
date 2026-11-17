"""Tests unitarios del clasificador de RFP.

Verifica que:
- Una RFP formal (con todos los indicadores) sea clasificada como válida.
- Una RFP informal (con indicadores mínimos) sea clasificada como válida.
- Un documento inválido (sin alcance, cliente ni servicio) sea descartado.
"""

from __future__ import annotations

from data.pipelines.rfp_intake.nodes import classifier
from data.pipelines.rfp_intake.state import RFPIntakeState


def _make_state(markdown: str) -> RFPIntakeState:
    return RFPIntakeState(
        ticket_id=1,
        pdf_path="/fake/path.pdf",
        markdown_content=markdown,
    )


# ─── Textos de prueba ─────────────────────────────────────────────────

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
- Menú de autor exclusivo
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

Saludos,
Andrés
"""

DOCUMENTO_INVALIDO = """# Consulta de Franquicia

Hola,

Estamos interesados en abrir una franquicia de Brasaland en nuestra ciudad.
Por favor envíennos información sobre los requisitos y costos de franquicia.

Gracias,
Juan Pérez
"""


# ─── Tests ────────────────────────────────────────────────────────────

class TestRFPPipeline:
    """Suite de tests para el pipeline de recepción RFP."""

    def test_clasificador_rfp_formal(self):
        """Una RFP formal con todos los indicadores debe ser válida."""
        state = _make_state(RFP_FORMAL)
        result = classifier(state)
        assert result.is_valid is True, "La RFP formal debería ser clasificada como válida"

    def test_clasificador_rfp_informal(self):
        """Una RFP informal con indicadores mínimos debe ser válida."""
        state = _make_state(RFP_INFORMAL)
        result = classifier(state)
        assert result.is_valid is True, "La RFP informal debería ser clasificada como válida"

    def test_clasificador_documento_invalido(self):
        """Un documento sin alcance, presupuesto ni fecha límite debe ser descartado."""
        state = _make_state(DOCUMENTO_INVALIDO)
        result = classifier(state)
        assert result.is_valid is False, (
            "El documento inválido debería ser descartado"
        )

    def test_clasificador_sin_contenido(self):
        """Si no hay contenido, el clasificador debe marcar error."""
        state = RFPIntakeState(ticket_id=1, pdf_path="/fake/path.pdf", markdown_content=None)
        result = classifier(state)
        assert result.error is not None
        assert result.error_node == "classifier"

    def test_clasificador_texto_vacio(self):
        """Texto vacío o mínimo no debe ser clasificado como RFP."""
        state = _make_state("")
        result = classifier(state)
        assert result.is_valid is False, "Texto vacío no es una RFP"