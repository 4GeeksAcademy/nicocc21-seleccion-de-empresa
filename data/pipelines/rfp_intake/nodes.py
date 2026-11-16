"""Nodos del pipeline rfp_intake.

Cada función es un nodo LangGraph que recibe y devuelve RFPIntakeState.
Los nodos son puros (sin side effects de I/O pesado) o gestionan su
propio side effect (escritura a DB, guardado de archivos).

Flujo:
  pdf_to_markdown → classifier → orchestrator → workers → synthesizer
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from markitdown import MarkItDown

from data.pipelines.rfp_intake.state import (
    DepartmentAnalysis,
    RFPIntakeState,
    ReadabilityMetrics,
    RFPMetadata as RFPMetadataState,
)

_logger = logging.getLogger(__name__)

# ─── Constantes ────────────────────────────────────────────────────────

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

DEPARTMENTS_REGISTRY = {
    "marketing": {
        "name": "Marketing y Experiencia Digital",
        "responsable": "Camila Ospina",
        "keywords": [
            "marca", "co-branding", "exclusividad", "términos de marca",
            "validez", "campaña", "marketing", "brand", "experiencia",
        ],
    },
    "operaciones": {
        "name": "Operaciones de Restaurante",
        "responsable": "Felipe Guerrero",
        "keywords": [
            "viabilidad", "cocina", "personal", "montaje", "operativo",
            "capacidad", "tiempos", "costo operativo", "evento",
        ],
    },
    "procurement": {
        "name": "Procurement y Proveedores",
        "responsable": "Lucía Fernández",
        "keywords": [
            "insumos", "proveedores", "volumen", "costo", "entrega",
            "suministro", "compra", "logística",
        ],
    },
    "training": {
        "name": "Training y Estándares de Calidad",
        "responsable": "Jake Morrison",
        "keywords": [
            "receta", "estándar", "certificación", "capacitación",
            "calidad", "entrenamiento", "menú nuevo", "desarrollo",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 1: PDF → Markdown
# ═══════════════════════════════════════════════════════════════════════

def pdf_to_markdown(state: RFPIntakeState) -> RFPIntakeState:
    """Convierte el PDF a Markdown usando MarkItDown.

    Guarda el resultado como archivo .md en data/raw/ y actualiza
    state.markdown_content y state.markdown_path.
    """
    pdf_path = Path(state.pdf_path)
    if not pdf_path.exists():
        state.error = f"PDF no encontrado: {state.pdf_path}"
        state.error_node = "pdf_to_markdown"
        return state

    try:
        md = MarkItDown()
        result = md.convert(str(pdf_path))
        markdown_text = result.text_content
    except Exception as exc:
        state.error = f"Error al convertir PDF a Markdown: {exc}"
        state.error_node = "pdf_to_markdown"
        return state

    # Guardar el Markdown como archivo
    md_filename = pdf_path.stem + ".md"
    md_path = RAW_DIR / md_filename
    try:
        md_path.write_text(markdown_text, encoding="utf-8")
    except Exception as exc:
        state.error = f"Error al guardar Markdown: {exc}"
        state.error_node = "pdf_to_markdown"
        return state

    state.markdown_content = markdown_text
    state.markdown_path = str(md_path)
    _logger.info("PDF convertido a Markdown: %s → %s", pdf_path.name, md_filename)

    return state


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 1b: Métricas de legibilidad
# ═══════════════════════════════════════════════════════════════════════

def compute_readability(state: RFPIntakeState) -> RFPIntakeState:
    """Calcula métricas de legibilidad sobre el Markdown convertido.

    Usa py-readability-metrics para estimar costo de procesamiento LLM.
    """
    if state.markdown_content is None:
        state.error = "No hay contenido Markdown para calcular legibilidad"
        state.error_node = "compute_readability"
        return state

    try:
        from readability import Readability as ReadabilityCalculator

        text = state.markdown_content

        # Limpiar el texto: eliminar cabeceras, enlaces, etc. para mejor
        # precisión en las métricas
        clean_text = re.sub(r"#{1,6}\s+", "", text)  # headers
        clean_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_text)  # links

        r = ReadabilityCalculator(clean_text)

        flesch_ease = r.flesch()
        flesch_kincaid = r.flesch_kincaid()
        gunning = r.gunning_fog()

        words = clean_text.split()
        sentences = re.split(r"[.!?]+", clean_text)

        state.readability = ReadabilityMetrics(
            flesch_reading_ease=round(flesch_ease.score, 2),
            flesch_kincaid_grade=round(flesch_kincaid.score, 2),
            gunning_fog=round(gunning.score, 2),
            word_count=len(words),
            sentence_count=len([s for s in sentences if s.strip()]),
        )
    except ImportError:
        _logger.warning("py-readability-metrics no instalado; se omite legibilidad")
        state.readability = ReadabilityMetrics(word_count=len(state.markdown_content.split()))
    except Exception as exc:
        _logger.warning("Error al calcular legibilidad: %s", exc)
        state.readability = ReadabilityMetrics(word_count=len(state.markdown_content.split()))

    return state


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 2: Clasificador
# ═══════════════════════════════════════════════════════════════════════

def classifier(state: RFPIntakeState) -> RFPIntakeState:
    """Clasifica el documento como RFP válida o no.

    Criterios de clasificación:
      - Debe mencionar un cliente/entidad solicitante
      - Debe describir un tipo de servicio (catering, concesión, co-branding, etc.)
      - Debe tener alcance o volumen (comensales, ubicaciones, duración)
      - Documentos sin alcance, presupuesto ni fecha límite → descartado

    NOTA: Este es un clasificador basado en heurísticas + LLM ligero.
    """
    if state.markdown_content is None:
        state.error = "No hay contenido para clasificar"
        state.error_node = "classifier"
        return state

    text = state.markdown_content.lower()

    # --- Heurísticas rápidas de descarte ---

    # 1. Sin mención de servicio o propuesta → probablemente inválido
    service_indicators = [
        "catering", "concesión", "concesion", "co-branding", "cobranding",
        "propuesta", "servicio", "menú", "menu", "restaurante",
        "suministro", "alimentación", "alimentacion",
    ]
    has_service = any(indicator in text for indicator in service_indicators)

    # 2. Sin mención de cliente o entidad
    client_indicators = [
        "solicitante", "cliente", "empresa", "entidad", "organización",
        "organizacion", "resort", "hotel", "compañía", "compania",
        "corporación", "corporacion",
    ]
    has_client = any(indicator in text for indicator in client_indicators)

    # 3. Sin alcance o volumen
    scope_indicators = [
        "comensales", "personas", "empleados", "ubicaciones",
        "resorts", "sucursales", "volumen", "alcance",
        "cobertura", "anual", "mensual", "semanal",
    ]
    has_scope = any(indicator in text for indicator in scope_indicators)

    # Decisión: se necesita al menos service + (client o scope)
    is_valid = has_service and (has_client or has_scope)

    if not is_valid:
        _logger.info(
            "Documento descartado: service=%s, client=%s, scope=%s",
            has_service, has_client, has_scope,
        )
        state.is_valid = False
        return state

    state.is_valid = True
    _logger.info("Documento clasificado como RFP válida")

    return state


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 3: Orquestador
# ═══════════════════════════════════════════════════════════════════════

def orchestrator(state: RFPIntakeState) -> RFPIntakeState:
    """Orquesta la descomposición del documento en workstreams por depto.

    Extrae metadatos básicos y decide qué departamentos aplicar.
    """
    if not state.is_valid or state.markdown_content is None:
        return state

    text = state.markdown_content
    text_lower = text.lower()

    # --- Extraer metadatos básicos ---
    metadata = RFPMetadataState()

    # Cliente: buscar primeras líneas o patrones comunes
    client_match = re.search(
        r"(?:solicitante|cliente|empresa|entidad)[:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)",
        text, re.IGNORECASE
    )
    if client_match:
        metadata.client_name = client_match.group(1).strip()

    # Si no se encontró con patrón, tomar primera línea significativa
    if not metadata.client_name:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:5]:
            if len(line) > 5 and not line.startswith("#"):
                metadata.client_name = line[:100]
                break

    # Ubicación
    location_match = re.search(
        r"(?:ubicación|ubicacion|localización|localizacion|locación|locacion|lugar|ciudad|sede)[:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ\s,]+)",
        text, re.IGNORECASE
    )
    if location_match:
        metadata.location = location_match.group(1).strip()

    # Tipo de servicio
    for stype in ["catering", "concesión", "concesion", "co-branding", "cobranding",
                   "suministro", "evento", "servicio recurrente"]:
        if stype in text_lower:
            metadata.service_type = stype
            break

    # Alcance
    scope_match = re.search(
        r"(?:alcance|volumen|cobertura)[:\s]+([^\n]+)",
        text, re.IGNORECASE
    )
    if scope_match:
        metadata.scope = scope_match.group(1).strip()

    # Deadline
    deadline_match = re.search(
        r"(?:fecha límite|fecha limite|deadline|fecha de respuesta|responder antes del?)[:\s]+([^\n]+)",
        text, re.IGNORECASE
    )
    if deadline_match:
        metadata.deadline = deadline_match.group(1).strip()

    # Presupuesto
    budget_match = re.search(
        r"(?:presupuesto|budget|rango|inversión|inversion)[:\s]*([\d,.kKmMbB\s$USDCOP+-]+)",
        text, re.IGNORECASE
    )
    if budget_match:
        metadata.budget_range = budget_match.group(1).strip()
        # Intentar extraer valores numéricos en USD
        usd_numbers = re.findall(r'(?:USD|\$)?\s*([\d,]+)\s*(?:USD|\$)?', text)
        usd_values = []
        for n in usd_numbers:
            try:
                val = float(n.replace(",", ""))
                if val > 100:
                    usd_values.append(val)
            except ValueError:
                pass
        if usd_values:
            metadata.budget_min_usd = min(usd_values)
            metadata.budget_max_usd = max(usd_values)

    # --- Decidir departamentos necesarios ---
    departments_needed = []

    # Marketing: siempre aplica (dueño del ticket)
    departments_needed.append("marketing")

    # Operaciones: si hay indicadores de servicio, volumen, cocina
    if any(kw in text_lower for kw in DEPARTMENTS_REGISTRY["operaciones"]["keywords"]):
        departments_needed.append("operaciones")

    # Procurement: si hay indicadores de insumos, costos, proveedores
    if any(kw in text_lower for kw in DEPARTMENTS_REGISTRY["procurement"]["keywords"]):
        departments_needed.append("procurement")

    # Training: si menciona receta nueva, menú nuevo, certificación, estándar nuevo
    training_keywords = ["receta", "menú nuevo", "menu nuevo", "nuevo estándar",
                         "nuevo estandar", "certificación", "certificacion",
                         "estándar de calidad", "estandar de calidad",
                         "desarrollo", "capacitación", "capacitacion",
                         "receta nueva", "estándar nuevo", "estandar nuevo"]
    if any(kw in text_lower for kw in training_keywords):
        departments_needed.append("training")

    metadata.departments_needed = departments_needed

    # --- Identificar campos faltantes ---
    open_questions = []
    if not metadata.client_name:
        open_questions.append("Nombre del cliente no especificado")
    if not metadata.location:
        open_questions.append("Ubicación no especificada")
    if not metadata.service_type:
        open_questions.append("Tipo de servicio no especificado")
    if not metadata.scope:
        open_questions.append("Alcance/volumen no especificado")
    if not metadata.deadline:
        open_questions.append("Fecha límite no especificada")
    if not metadata.budget_range:
        open_questions.append("Presupuesto no especificado")
    metadata.open_questions = open_questions

    state.rfp_metadata = metadata
    _logger.info(
        "Documento orquestado: cliente=%s, servicio=%s, deptos=%s, open_qs=%d",
        metadata.client_name, metadata.service_type,
        metadata.departments_needed, len(open_questions),
    )

    return state


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 4: Workers por departamento
# ═══════════════════════════════════════════════════════════════════════

def worker_marketing(state: RFPIntakeState) -> RFPIntakeState:
    """Worker de Marketing: extrae aspectos de marca, exclusividad, co-branding."""
    text = state.markdown_content or ""
    aspects = _extract_section_by_keywords(text, DEPARTMENTS_REGISTRY["marketing"]["keywords"])
    aspects.update({
        "departamento": "Marketing y Experiencia Digital",
        "responsable": "Camila Ospina",
        "ticket_owner": True,
    })
    state.department_analyses.append(
        DepartmentAnalysis(department_id="marketing", key_aspects=aspects)
    )
    return state


def worker_operaciones(state: RFPIntakeState) -> RFPIntakeState:
    """Worker de Operaciones: extrae aspectos de viabilidad operativa."""
    text = state.markdown_content or ""
    aspects = _extract_section_by_keywords(text, DEPARTMENTS_REGISTRY["operaciones"]["keywords"])
    aspects.update({
        "departamento": "Operaciones de Restaurante",
        "responsable": "Felipe Guerrero",
    })
    state.department_analyses.append(
        DepartmentAnalysis(department_id="operaciones", key_aspects=aspects)
    )
    return state


def worker_procurement(state: RFPIntakeState) -> RFPIntakeState:
    """Worker de Procurement: extrae aspectos de insumos, costos, proveedores."""
    text = state.markdown_content or ""
    aspects = _extract_section_by_keywords(text, DEPARTMENTS_REGISTRY["procurement"]["keywords"])
    aspects.update({
        "departamento": "Procurement y Proveedores",
        "responsable": "Lucía Fernández",
    })
    state.department_analyses.append(
        DepartmentAnalysis(department_id="procurement", key_aspects=aspects)
    )
    return state


def worker_training(state: RFPIntakeState) -> RFPIntakeState:
    """Worker de Training: extrae aspectos de recetas, estándares, certificaciones."""
    text = state.markdown_content or ""
    aspects = _extract_section_by_keywords(text, DEPARTMENTS_REGISTRY["training"]["keywords"])
    aspects.update({
        "departamento": "Training y Estándares de Calidad",
        "responsable": "Jake Morrison",
    })
    state.department_analyses.append(
        DepartmentAnalysis(department_id="training", key_aspects=aspects)
    )
    return state


def _extract_section_by_keywords(text: str, keywords: list[str]) -> dict:
    """Extrae párrafos relevantes del texto según palabras clave."""
    relevant_paragraphs = []
    paragraphs = re.split(r"\n\s*\n", text)

    for para in paragraphs:
        para_lower = para.lower()
        if any(kw in para_lower for kw in keywords):
            # Limitar a 500 chars por párrafo
            truncated = para.strip()[:500]
            if truncated:
                relevant_paragraphs.append(truncated)

    return {
        "extractos_relevantes": relevant_paragraphs[:5],  # máximo 5 párrafos
        "total_extractos": len(relevant_paragraphs),
        "notas": "Basado en palabras clave del departamento. "
                 "No inventar cifras no presentes en el documento original.",
    }


# ═══════════════════════════════════════════════════════════════════════
#  Nodo 5: Synthesizer
# ═══════════════════════════════════════════════════════════════════════

def synthesizer(state: RFPIntakeState) -> RFPIntakeState:
    """Consolida el análisis de todos los departamentos en un resumen.

    Produce un texto estructurado que Ventas (Marketing) puede leer
    para saber qué le toca a cada departamento y a quién pedírselo.
    """
    if not state.is_valid:
        return state

    metadata = state.rfp_metadata
    lines: list[str] = []

    lines.append("# Resumen de Análisis de RFP")
    lines.append("")
    lines.append(f"**Cliente:** {metadata.client_name or 'No especificado'}")
    lines.append(f"**Ubicación:** {metadata.location or 'No especificada'}")
    lines.append(f"**Tipo de servicio:** {metadata.service_type or 'No especificado'}")
    lines.append(f"**Alcance:** {metadata.scope or 'No especificado'}")
    lines.append(f"**Fecha límite:** {metadata.deadline or 'No especificada'}")
    lines.append(f"**Presupuesto:** {metadata.budget_range or 'No especificado'}")
    lines.append("")
    lines.append("## Departamentos involucrados")
    lines.append("")

    # Agrupar analyses por departamento
    analyses_by_dept = {a.department_id: a for a in state.department_analyses}

    for dept_id in metadata.departments_needed:
        dept_info = DEPARTMENTS_REGISTRY.get(dept_id, {})
        dept_name = dept_info.get("name", dept_id)
        responsable = dept_info.get("responsable", "No asignado")
        analysis = analyses_by_dept.get(dept_id)

        lines.append(f"### {dept_name}")
        lines.append(f"**Responsable:** {responsable}")
        lines.append("")
        if analysis and analysis.key_aspects.get("extractos_relevantes"):
            lines.append("**Aspectos clave:**")
            for extract in analysis.key_aspects["extractos_relevantes"][:3]:
                lines.append(f"- {extract[:200]}")
        else:
            lines.append("*No se identificaron aspectos específicos para este departamento.*")
        lines.append("")

    # Preguntas abiertas
    if metadata.open_questions:
        lines.append("## Información faltante")
        lines.append("")
        for q in metadata.open_questions:
            lines.append(f"- ⚠️ {q}")
        lines.append("")

    lines.append("## Handoff para Parte 2")
    lines.append("")
    lines.append(f"- `ticket_id`: {state.ticket_id}")
    lines.append(f"- `departments_needed`: {json.dumps(metadata.departments_needed)}")
    lines.append(f"- `key_aspects` disponibles por departamento en DB")
    lines.append("- El generador de cada departamento recibirá metadatos + extractos relevantes")

    state.final_summary = "\n".join(lines)
    _logger.info(
        "Synthesizer completado para ticket %d con %d departamentos",
        state.ticket_id, len(metadata.departments_needed),
    )

    return state


# ═══════════════════════════════════════════════════════════════════════
#  Helpers de persistencia
# ═══════════════════════════════════════════════════════════════════════

def persist_ticket(state: RFPIntakeState) -> None:
    """Persiste el resultado del pipeline en PostgreSQL.

    Se llama desde el grafo después de que todos los nodos terminen.
    Actualiza:
      - Ticket.status
      - RFPMetadata (metadatos + legibilidad)
      - DepartmentSection.key_aspects (por cada departamento)
    """
    from sqlmodel import Session

    from services.brasaland_api.database import engine
    from services.brasaland_api.rfp_models import (
        DepartmentSection as DepartmentSectionORM,
        RFPMetadata as RFPMetadataORM,
        Ticket as TicketORM,
    )

    with Session(engine) as session:
        # 1. Actualizar ticket
        ticket = session.get(TicketORM, state.ticket_id)
        if ticket is None:
            _logger.error("Ticket %d no encontrado en DB", state.ticket_id)
            return

        if state.error:
            ticket.status = "descartado"
            ticket.error_message = state.error
        elif state.is_valid is False:
            ticket.status = "descartado"
        elif state.is_valid is True and state.final_summary:
            ticket.status = "analisis_completo"

        if state.markdown_path:
            ticket.markdown_path = state.markdown_path

        session.add(ticket)

        # 2. Guardar/actualizar metadatos
        if state.is_valid and state.rfp_metadata:
            meta = state.rfp_metadata
            existing_meta = session.exec(
                f"SELECT id FROM rfp_metadata WHERE ticket_id = {state.ticket_id}"
            ).first()

            rfpm = RFPMetadataORM(
                ticket_id=state.ticket_id,
                client_name=meta.client_name,
                location=meta.location,
                service_type=meta.service_type,
                scope=meta.scope,
                deadline=meta.deadline,
                budget_range=meta.budget_range,
                budget_min_usd=meta.budget_min_usd,
                budget_max_usd=meta.budget_max_usd,
                departments_needed=json.dumps(meta.departments_needed),
                flesch_reading_ease=state.readability.flesch_reading_ease if state.readability else None,
                flesch_kincaid_grade=state.readability.flesch_kincaid_grade if state.readability else None,
                gunning_fog=state.readability.gunning_fog if state.readability else None,
                word_count=state.readability.word_count if state.readability else None,
                sentence_count=state.readability.sentence_count if state.readability else None,
            )
            if existing_meta and hasattr(existing_meta, "id"):
                rfpm.id = existing_meta.id
                session.merge(rfpm)
            else:
                session.add(rfpm)

        # 3. Guardar key_aspects por departamento
        for analysis in state.department_analyses:
            existing_section = session.exec(
                f"SELECT id FROM rfp_department_sections "
                f"WHERE ticket_id = {state.ticket_id} AND department_id = '{analysis.department_id}'"
            ).first()

            dept_section = DepartmentSectionORM(
                ticket_id=state.ticket_id,
                department_id=analysis.department_id,
                key_aspects=json.dumps(analysis.key_aspects, ensure_ascii=False),
            )
            if existing_section and hasattr(existing_section, "id"):
                dept_section.id = existing_section.id
                session.merge(dept_section)
            else:
                session.add(dept_section)

        session.commit()
        _logger.info("Pipeline persistido para ticket %d (status=%s)", state.ticket_id, ticket.status)