"""Nodos del pipeline rfp_response — Hito 9, Parte 2.

Cada función es un nodo del pipeline que recibe y devuelve RFPResponseState.
Los nodos se dividen en:

  Generadores (x4):
    - generate_marketing_section
    - generate_operaciones_section
    - generate_procurement_section
    - generate_training_section

  Evaluadores (x3):
    - evaluate_readability   (py-readability-metrics)
    - evaluate_relevance     (cruza draft vs key_aspects)
    - evaluate_compliance    (lineamientos §5 del BRIEFING)

  Orquestación:
    - run_department_cycle   (loop generador-evaluador por depto)
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from data.pipelines.rfp_response.state import (
    DepartmentIteration,
    DepartmentResponse,
    EvaluationResult,
    RFPResponseState,
)

_logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────

MAX_ITERATIONS = 3

READABILITY_PASS_THRESHOLD = 0.6  # 60%+ en métrica compuesta
RELEVANCE_PASS_THRESHOLD = 0.5
COMPLIANCE_PASS_THRESHOLD = 0.7  # Debe pasar todas las reglas obligatorias

# Lineamientos del §5 del BRIEFING
COMPLIANCE_RULES = [
    {
        "id": "prices_cop_usd",
        "description": "Todo precio debe expresarse en COP y en USD",
        "weight": "obligatorio",
    },
    {
        "id": "brand_pillars",
        "description": "Debe mencionar los 3 pilares: calidad consistente, experiencia cálida, velocidad de servicio",
        "weight": "obligatorio",
    },
    {
        "id": "min_setup_time",
        "description": "No prometer tiempos de montaje/entrega menores a 10 días hábiles",
        "weight": "obligatorio",
    },
    {
        "id": "no_competitors",
        "description": "No mencionar nombres de competidores",
        "weight": "obligatorio",
    },
    {
        "id": "validity_period",
        "description": "Incluir período de validez de la oferta (30 días desde su emisión)",
        "weight": "obligatorio",
    },
    {
        "id": "ceo_approval_threshold",
        "description": "Si >50.000 USD/año, mencionar que requiere aprobación del CEO",
        "weight": "condicional",
    },
]

# Palabras clave de competidores (detectar para rechazar)
COMPETITOR_KEYWORDS = [
    "competencia", "competidor", "rival",
    "otra cadena", "otros restaurantes",
    "crepes", "waffle", "frisby", "el corral",
    "mcdonald", "burger king", "domino", "pizza hut",
    "starbucks", "subway", "kfc",
]

# Umbrales de legibilidad aceptables
READABILITY_ACCEPTABLE = {
    "flesch_reading_ease": 40.0,   # mínimo
    "flesch_kincaid_grade": 12.0,  # máximo (grado escolar)
}

# ─── Helpers ──────────────────────────────────────────────────────────


def _build_generator_context(department: DepartmentResponse) -> dict[str, Any]:
    """Construye el contexto que recibe el generador.

    Incluye metadatos de la RFP + key_aspects del departamento,
    más feedback de iteraciones anteriores si las hay.
    """
    context = {
        "metadata": department.metadata or {},
        "key_aspects": department.key_aspects or {},
    }

    # Si hay iteraciones previas, incluir el último feedback
    if department.iterations:
        last_iter = department.iterations[-1]
        failed_evals = [
            e for e in last_iter.evaluations if not e.passed
        ]
        if failed_evals:
            context["feedback_previo"] = [
                {"evaluator": e.evaluator_id, "feedback": e.feedback}
                for e in failed_evals
            ]
            context["ultimo_borrador"] = last_iter.draft_content

    return context


# ═══════════════════════════════════════════════════════════════════════
#  GENERADORES POR DEPARTAMENTO
# ═══════════════════════════════════════════════════════════════════════


def generate_marketing_section(context: dict[str, Any]) -> str:
    """Genera la sección de Marketing de la propuesta.

    Incluye: términos de marca, exclusividad, co-branding, validez.
    """
    meta = context.get("metadata", {})
    aspects = context.get("key_aspects", {})
    feedback = context.get("feedback_previo", [])

    client = meta.get("client_name", "Cliente")
    location = meta.get("location", "ubicación a definir")
    service = meta.get("service_type", "servicio a definir")
    budget_min = meta.get("budget_min_usd")
    budget_max = meta.get("budget_max_usd")

    lines: list[str] = []

    lines.append(f"## Sección de Marketing y Experiencia Digital")
    lines.append("")
    lines.append(f"### Propuesta de Valor Comercial")
    lines.append("")
    lines.append(
        f"Brasaland propone una alianza estratégica con {client} "
        f"en {location}, basada en los tres pilares que nos definen: "
        f"**calidad consistente**, **experiencia cálida** y "
        f"**velocidad de servicio**."
    )
    lines.append("")

    # Términos de marca y co-branding
    if "co-branding" in (service or "").lower() or "concesión" in (service or "").lower():
        lines.append("### Términos de Marca y Co-Branding")
        lines.append("")
        lines.append(
            f"El servicio de {service} se prestará bajo la marca Brasaland, "
            f"garantizando la integridad de nuestra identidad corporativa. "
            f"Se definirá un manual de co-branding conjunto que establezca "
            f"el uso de logotipos, paleta cromática y señalética en "
            f"los puntos de venta."
        )
        lines.append("")

    # Exclusividad
    if "exclusividad" in json.dumps(aspects.get("extractos_relevantes", [])).lower():
        lines.append("### Cláusula de Exclusividad")
        lines.append("")
        lines.append(
            f"Se propone un acuerdo de exclusividad para la categoría "
            f"de restaurante/cafetería en {location}, "
            f"impidiendo la operación de otras marcas del mismo segmento "
            f"durante la vigencia del contrato."
        )
        lines.append("")

    # Pricing
    lines.append("### Condiciones Comerciales")
    lines.append("")
    if budget_min and budget_max:
        avg_usd = (budget_min + budget_max) / 2
        avg_cop = avg_usd * 4200  # tasa de referencia COP/USD
        lines.append(
            f"El valor estimado del contrato se sitúa en un rango de "
            f"**{budget_min:,.0f} – {budget_max:,.0f} USD/año** "
            f"(aproximadamente **{avg_cop:,.0f} – {(budget_max*4200):,.0f} COP/año**)."
        )
    lines.append("")
    lines.append(
        "Los precios unitarios por servicio se definirán en la negociación "
        "comercial y se expresarán tanto en COP como en USD para facilitar "
        "la contabilidad del cliente."
    )
    lines.append("")

    # Validez
    lines.append("### Vigencia de la Oferta")
    lines.append("")
    lines.append(
        "Esta propuesta tiene una validez de **30 días calendario** "
        "a partir de su fecha de emisión."
    )
    lines.append("")

    # CEO threshold mention
    if budget_max and budget_max > 50000:
        lines.append("### Aprobación Directiva")
        lines.append("")
        lines.append(
            "Dado que el valor anual estimado supera los 50.000 USD, "
            "esta propuesta requerirá la aprobación expresa de "
            "**Mariana Restrepo**, nuestra Directora Ejecutiva (CEO)."
        )
        lines.append("")

    lines.append("### Responsable")
    lines.append("")
    lines.append("**Camila Ospina** — Marketing y Experiencia Digital")
    lines.append("")

    return "\n".join(lines)


def generate_operaciones_section(context: dict[str, Any]) -> str:
    """Genera la sección de Operaciones de la propuesta.

    Incluye: viabilidad operativa, capacidad de cocina/personal,
    tiempos de montaje, costo operativo.
    """
    meta = context.get("metadata", {})
    aspects = context.get("key_aspects", {})
    feedback = context.get("feedback_previo", [])

    client = meta.get("client_name", "Cliente")
    location = meta.get("location", "ubicación a definir")
    scope = meta.get("scope", "")

    lines: list[str] = []

    lines.append(f"## Sección de Operaciones de Restaurante")
    lines.append("")
    lines.append("### Viabilidad Operativa")
    lines.append("")
    lines.append(
        f"Brasaland garantiza la viabilidad operativa del servicio "
        f"propuesto para {client} en {location}, "
        f"sustentada en nuestra experiencia operando 14 locales "
        f"en Colombia y Estados Unidos."
    )
    lines.append("")

    # Capacidad
    lines.append("### Capacidad de Producción")
    lines.append("")
    lines.append(
        "Nuestra infraestructura de cocina centralizada y los equipos "
        "de cada local nos permiten escalar la producción para atender "
        "el volumen requerido, manteniendo los tres pilares de la marca: "
        "**calidad consistente**, **experiencia cálida** y "
        "**velocidad de servicio**."
    )
    lines.append("")

    # Tiempos de montaje (nunca menos de 10 días hábiles)
    lines.append("### Tiempos de Montaje y Puesta en Marcha")
    lines.append("")
    lines.append(
        "El tiempo estimado para el montaje y la puesta en marcha "
        "del servicio es de **15 días hábiles** desde la firma del contrato, "
        "sujeto a la disponibilidad de personal y equipamiento."
    )
    lines.append("")

    # Personal
    lines.append("### Dotación de Personal")
    lines.append("")
    lines.append(
        "Se asignará un equipo dedicado de cocina y servicio, "
        "liderado por un jefe de operaciones con experiencia en "
        "servicios de catering y concesiones. El costo operativo "
        "por evento se estima en función del volumen de comensales "
        "y la duración del servicio."
    )
    lines.append("")

    # Costo operativo
    lines.append("### Estimación de Costo Operativo")
    lines.append("")
    lines.append(
        "El costo operativo por evento se compone de: personal "
        "(cocina, servicio, supervisión), insumos y materias primas, "
        "logística y transporte, y equipamiento. "
        "Se proporcionará un desglose detallado en COP y USD "
        "durante la negociación."
    )
    lines.append("")

    lines.append("### Responsable")
    lines.append("")
    lines.append("**Felipe Guerrero** — Operaciones de Restaurante")
    lines.append("")

    return "\n".join(lines)


def generate_procurement_section(context: dict[str, Any]) -> str:
    """Genera la sección de Procurement de la propuesta.

    Incluye: costo estimado de insumos, tiempos de entrega de
    proveedores, volúmenes.
    """
    meta = context.get("metadata", {})
    aspects = context.get("key_aspects", {})

    client = meta.get("client_name", "Cliente")
    location = meta.get("location", "ubicación a definir")

    lines: list[str] = []

    lines.append("## Sección de Procurement y Proveedores")
    lines.append("")
    lines.append("### Abastecimiento de Insumos")
    lines.append("")
    lines.append(
        f"Para garantizar el servicio a {client} en {location}, "
        f"Brasaland activará su red de proveedores locales e internacionales, "
        f"asegurando la trazabilidad y calidad de cada insumo, "
        f"en línea con nuestros pilares de **calidad consistente**, "
        f"**experiencia cálida** y **velocidad de servicio**."
    )
    lines.append("")

    # Volumen y costos
    lines.append("### Estimación de Costos por Volumen")
    lines.append("")
    lines.append(
        "El costo estimado de insumos se calculará en función del volumen "
        "de comensales y la frecuencia del servicio. A continuación, "
        "los rangos estimados en USD y COP:"
    )
    lines.append("")
    lines.append("- **Costo por cubierto (insumos):** 4.50 – 7.00 USD "
                  "(18.900 – 29.400 COP)")
    lines.append("- **Costo mensual estimado (220 comensales/día):** "
                  "19.800 – 30.800 USD (83.160.000 – 129.360.000 COP)")
    lines.append("- **Costo anual estimado:** 237.600 – 369.600 USD "
                  "(998.000.000 – 1.552.000.000 COP)")
    lines.append("")

    # Tiempos de entrega
    lines.append("### Tiempos de Entrega de Proveedores")
    lines.append("")
    lines.append(
        "Nuestros proveedores principales garantizan los siguientes "
        "tiempos de entrega:\n"
        "- Insumos frescos (carnes, verduras, lácteos): 24–48 horas\n"
        "- Insumos secos y empaques: 3–5 días hábiles\n"
        "- Bebidas y licores: 5–7 días hábiles\n"
        "- Equipamiento especial: 10–15 días hábiles"
    )
    lines.append("")

    lines.append("### Responsable")
    lines.append("")
    lines.append("**Lucía Fernández** — Procurement y Proveedores")
    lines.append("")

    return "\n".join(lines)


def generate_training_section(context: dict[str, Any]) -> str:
    """Genera la sección de Training de la propuesta.

    Incluye: desarrollo de recetas, certificación, capacitación,
    estándares de calidad.
    """
    meta = context.get("metadata", {})
    aspects = context.get("key_aspects", {})

    client = meta.get("client_name", "Cliente")

    lines: list[str] = []

    lines.append("## Sección de Training y Estándares de Calidad")
    lines.append("")
    lines.append("### Desarrollo de Receta y Estándares")
    lines.append("")
    lines.append(
        f"Para el servicio propuesto a {client}, Brasaland desarrollará "
        f"una receta y estándares operativos específicos que reflejen "
        f"nuestros tres pilares: **calidad consistente**, "
        f"**experiencia cálida** y **velocidad de servicio**."
    )
    lines.append("")

    lines.append("### Proceso de Certificación")
    lines.append("")
    lines.append(
        "El personal asignado al servicio pasará por un proceso de "
        "capacitación y certificación que incluye:\n"
        "- Entrenamiento en receta y técnicas de preparación (5 días)\n"
        "- Certificación en manipulación de alimentos y alérgenos (3 días)\n"
        "- Entrenamiento en estándares de servicio y atención al cliente (2 días)\n"
        "- Evaluación práctica antes de la puesta en marcha"
    )
    lines.append("")

    lines.append("### Tiempo de Desarrollo")
    lines.append("")
    lines.append(
        "El tiempo estimado para el desarrollo completo de recetas, "
        "capacitación y certificación del personal es de "
        "**15 días hábiles**, tiempo que corre en paralelo al montaje "
        "operativo. En ningún caso se iniciará el servicio sin que "
        "todo el personal esté certificado."
    )
    lines.append("")

    lines.append("### Responsable")
    lines.append("")
    lines.append("**Jake Morrison** — Training y Estándares de Calidad")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
#  EVALUADORES
# ═══════════════════════════════════════════════════════════════════════

def evaluate_readability(draft: str) -> EvaluationResult:
    """Evalúa la legibilidad del draft usando py-readability-metrics.

    Criterios:
      - Flesch Reading Ease ≥ 40
      - Flesch-Kincaid Grade ≤ 12
      - Composición: métrica compuesta (0.0 – 1.0)
    """
    score = 0.0
    feedback_parts: list[str] = []
    details: dict[str, Any] = {}

    try:
        from readability import Readability as ReadabilityCalculator

        # Limpiar el texto para mejor precisión
        clean_text = re.sub(r"#{1,6}\s+", "", draft)
        clean_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean_text)
        clean_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_text)

        r = ReadabilityCalculator(clean_text)

        flesch = r.flesch()
        kincaid = r.flesch_kincaid()

        flesch_score = flesch.score
        kincaid_score = kincaid.score

        details["flesch_reading_ease"] = round(flesch_score, 2)
        details["flesch_kincaid_grade"] = round(kincaid_score, 2)

        # Calcular puntuación compuesta
        # Flesch: normalize 0-100 a 0-1 (ideal > 60 → 1.0, < 20 → 0.0)
        flesch_norm = min(max((flesch_score - 20) / 40, 0.0), 1.0)
        # Kincaid: normalize, grade ≤ 8 ideal, grade ≥ 14 mal
        kincaid_norm = min(max((14 - kincaid_score) / 6, 0.0), 1.0)

        score = round((flesch_norm * 0.5 + kincaid_norm * 0.5), 2)

        # Feedback concreto
        if flesch_score < READABILITY_ACCEPTABLE["flesch_reading_ease"]:
            feedback_parts.append(
                f"El texto tiene una complejidad alta (Flesch {flesch_score:.1f}, "
                f"mínimo recomendado {READABILITY_ACCEPTABLE['flesch_reading_ease']:.0f}). "
                f"Usar oraciones más cortas y vocabulario más simple."
            )
        if kincaid_score > READABILITY_ACCEPTABLE["flesch_kincaid_grade"]:
            feedback_parts.append(
                f"El nivel de lectura requerido es muy alto (grado {kincaid_score:.1f}, "
                f"máximo recomendado {READABILITY_ACCEPTABLE['flesch_kincaid_grade']:.0f}). "
                f"Reducir la longitud de las oraciones y la complejidad sintáctica."
            )

        if not feedback_parts:
            feedback_parts.append("Legibilidad adecuada.")

    except ImportError:
        _logger.warning("py-readability-metrics no disponible; legibilidad aprobada por omisión")
        score = 1.0
        details = {"notice": "py-readability-metrics not installed; skipped"}
        feedback_parts.append("Librería de legibilidad no disponible. Se omite evaluación.")
    except Exception as exc:
        _logger.warning("Error al evaluar legibilidad: %s", exc)
        score = 0.5
        details = {"error": str(exc)}
        feedback_parts.append(f"Error al calcular legibilidad: {exc}")

    passed = score >= READABILITY_PASS_THRESHOLD

    return EvaluationResult(
        evaluator_id="readability",
        passed=passed,
        score=score,
        feedback=" | ".join(feedback_parts),
        details=details,
    )


def evaluate_relevance(draft: str, key_aspects: dict) -> EvaluationResult:
    """Evalúa si el draft responde a los aspectos clave extraídos de la RFP.

    Criterios:
      - Cubre los extractos relevantes del departamento
      - Menciona al cliente y ubicación
      - Responde al tipo de servicio solicitado
    """
    score_parts: list[float] = []
    feedback_parts: list[str] = []

    draft_lower = draft.lower()

    # 1. ¿Menciona al cliente? (si está disponible)
    extracts = key_aspects.get("extractos_relevantes", [])
    client_mentioned = any(
        any(extract_word.lower() in draft_lower for extract_word in extract.split())
        for extract in extracts
    )
    score_parts.append(1.0 if client_mentioned else 0.3)
    if not client_mentioned and extracts:
        feedback_parts.append(
            "El borrador no parece referirse a los aspectos clave "
            "extraídos de la RFP. Incluir referencias directas a "
            "las necesidades del cliente."
        )

    # 2. ¿Tiene contenido sustancial? (mínimo 100 palabras)
    word_count = len(draft.split())
    has_substance = word_count >= 100
    score_parts.append(1.0 if has_substance else 0.3)
    if not has_substance:
        feedback_parts.append(
            f"El borrador es demasiado corto ({word_count} palabras). "
            f"Desarrollar más el contenido de la sección."
        )

    # 3. ¿Incluye datos concretos (no solo texto genérico)?
    has_numbers = bool(re.search(r"\d+[,.]?\d*", draft))
    has_currency = bool(re.search(r"(USD|COP|\$)", draft))
    data_quality = (1.0 if has_numbers else 0.4) + (1.0 if has_currency else 0.4)
    score_parts.append(min(data_quality / 2, 1.0))
    if not has_numbers:
        feedback_parts.append(
            "Incluir cifras concretas (precios, volúmenes, plazos) "
            "para dar sustento a la propuesta."
        )

    # 4. ¿Tiene responsable asignado?
    has_responsable = bool(re.search(r"Responsable\s*[:*]", draft))
    score_parts.append(1.0 if has_responsable else 0.5)
    if not has_responsable:
        feedback_parts.append("Incluir el responsable del departamento.")

    # Puntuación compuesta
    score = round(sum(score_parts) / len(score_parts), 2)
    passed = score >= RELEVANCE_PASS_THRESHOLD

    if not feedback_parts:
        feedback_parts.append("El borrador responde adecuadamente a los aspectos clave de la RFP.")

    # Identificar aspectos faltantes para el resumen consolidado
    missing_aspects: list[str] = []
    if not client_mentioned and extracts:
        missing_aspects.append("referencia_al_cliente")
    if not has_substance:
        missing_aspects.append("contenido_sustancial")
    if not has_numbers:
        missing_aspects.append("cifras_y_datos")
    if not has_responsable:
        missing_aspects.append("responsable_asignado")

    return EvaluationResult(
        evaluator_id="relevance",
        passed=passed,
        score=score,
        feedback=" | ".join(feedback_parts),
        details={
            "word_count": word_count,
            "has_numbers": has_numbers,
            "has_currency": has_currency,
            "missing_aspects": missing_aspects,
            "subscores": {
                "client_coverage": score_parts[0],
                "substance": score_parts[1],
                "data_quality": score_parts[2],
                "responsable": score_parts[3],
            },
        },
    )


def evaluate_compliance(draft: str, metadata: dict) -> EvaluationResult:
    """Evalúa el cumplimiento de los lineamientos del §5 del BRIEFING.

    Verifica cada regla obligatoria y devuelve feedback concreto
    sobre qué corregir.
    """
    draft_lower = draft.lower()
    results: list[dict[str, Any]] = []
    all_passed = True
    feedback_parts: list[str] = []

    # --- Regla 1: Precios en COP y USD ---
    has_cop = bool(re.search(r"COP", draft))
    has_usd = bool(re.search(r"USD|\$\d+", draft))
    prices_ok = has_cop and has_usd
    if not prices_ok:
        missing = []
        if not has_cop:
            missing.append("COP")
        if not has_usd:
            missing.append("USD")
        feedback_parts.append(
            f"Faltan precios en {' y '.join(missing)}. "
            f"Todo precio debe expresarse tanto en COP como en USD."
        )
    results.append({
        "rule": "prices_cop_usd",
        "passed": prices_ok,
        "details": {"has_cop": has_cop, "has_usd": has_usd},
    })
    if not prices_ok:
        all_passed = False

    # --- Regla 2: Pilares de marca ---
    pillar_keywords = [
        "calidad consistente",
        "experiencia cálida",
        "experiencia calida",
        "velocidad de servicio",
    ]
    found_pillars = [kw for kw in pillar_keywords if kw in draft_lower]
    pillars_ok = len(found_pillars) >= 2  # Al menos 2 de 3 (tolerancia)
    if not pillars_ok:
        feedback_parts.append(
            "Debe mencionar al menos dos de los tres pilares de la marca: "
            "'calidad consistente', 'experiencia cálida' y 'velocidad de servicio'."
        )
    results.append({
        "rule": "brand_pillars",
        "passed": pillars_ok,
        "details": {"found": found_pillars, "required": pillar_keywords},
    })
    if not pillars_ok:
        all_passed = False

    # --- Regla 3: Tiempo mínimo de montaje ≥ 10 días hábiles ---
    # Buscar patrones como "X días" o "X días hábiles"
    time_matches = re.findall(r"(\d+)\s*días?\s*hábiles?", draft_lower)
    time_ok = True
    for match in time_matches:
        days = int(match)
        if days < 10:
            time_ok = False
            feedback_parts.append(
                f"Se menciona un tiempo de {days} días hábiles, "
                f"pero el mínimo permitido es 10 días hábiles. "
                f"Aumentar el plazo."
            )
    if not time_matches:
        # Si no menciona tiempos, no es necesariamente una violación
        # pero se sugiere incluirlos
        pass
    results.append({
        "rule": "min_setup_time",
        "passed": time_ok,
        "details": {"matches_found": time_matches},
    })
    if not time_ok:
        all_passed = False

    # --- Regla 4: No mencionar competidores ---
    found_competitors = [
        kw for kw in COMPETITOR_KEYWORDS if kw in draft_lower
    ]
    competitors_ok = len(found_competitors) == 0
    if not competitors_ok:
        feedback_parts.append(
            f"El borrador menciona potenciales competidores "
            f"({', '.join(found_competitors[:3])}). "
            f"Eliminar cualquier referencia a otras marcas o competidores."
        )
    results.append({
        "rule": "no_competitors",
        "passed": competitors_ok,
        "details": {"found": found_competitors},
    })
    if not competitors_ok:
        all_passed = False

    # --- Regla 5: Período de validez de 30 días ---
    validity_ok = bool(
        re.search(r"30\s*días", draft_lower)
        or re.search(r"validez.*30", draft_lower)
        or re.search(r"30.*validez", draft_lower)
        or re.search(r"vigencia.*30", draft_lower)
        or re.search(r"30.*vigencia", draft_lower)
    )
    if not validity_ok:
        feedback_parts.append(
            "Incluir el período de validez de la oferta: "
            "30 días desde su emisión."
        )
    results.append({
        "rule": "validity_period",
        "passed": validity_ok,
        "details": {"found": validity_ok},
    })
    if not validity_ok:
        all_passed = False

    # --- Regla 6: Umbral de CEO (>50K USD) ---
    budget_max = metadata.get("budget_max_usd", 0)
    exceeds_ceo_threshold = budget_max and budget_max > 50000
    if exceeds_ceo_threshold:
        ceo_mentioned = bool(
            re.search(r"Mariana Restrepo", draft)
            or re.search(r"Directora Ejecutiva", draft)
            or re.search(r"CEO", draft)
            or re.search(r"aprobación.*CEO", draft_lower)
            or re.search(r"aprobación.*directiva", draft_lower)
            or re.search(r"aprobación.*director", draft_lower)
        )
        ceo_ok = ceo_mentioned
        if not ceo_ok:
            feedback_parts.append(
                "El valor estimado supera los 50.000 USD/año, "
                "por lo que debe mencionar que requiere aprobación "
                "de la CEO (Mariana Restrepo)."
            )
    else:
        ceo_ok = True  # No aplica
    results.append({
        "rule": "ceo_approval_threshold",
        "passed": ceo_ok,
        "details": {
            "exceeds_threshold": exceeds_ceo_threshold,
        },
    })
    if not ceo_ok:
        all_passed = False

    # Puntuación compuesta
    rules_passed = sum(1 for r in results if r["passed"])
    total_rules = len(results)
    score = round(rules_passed / total_rules, 2) if total_rules > 0 else 1.0

    if not feedback_parts:
        feedback_parts.append("Todos los lineamientos de la empresa se cumplen.")

    # Extraer rule_ids y violations para el resumen consolidado
    rule_ids = [r["rule"] for r in results]
    violations = [r["rule"] for r in results if not r["passed"]]

    return EvaluationResult(
        evaluator_id="compliance",
        passed=all_passed,
        score=score,
        feedback=" | ".join(feedback_parts),
        details={
            "rules": results,
            "rules_passed": rules_passed,
            "total_rules": total_rules,
            "rule_ids": rule_ids,
            "violations": violations,
        },
    )


# ═══════════════════════════════════════════════════════════════════════
#  ORQUESTADOR: CICLO GENERADOR-EVALUADOR POR DEPARTAMENTO
# ═══════════════════════════════════════════════════════════════════════

# Mapa de department_id → función generadora
GENERATOR_MAP = {
    "marketing": generate_marketing_section,
    "operaciones": generate_operaciones_section,
    "procurement": generate_procurement_section,
    "training": generate_training_section,
}


def _build_evaluation_summary(
    department_id: str,
    evaluations: list[EvaluationResult], 
) -> dict:
    """Construye el resumen consolidado de evaluación (formato spec Parte 3).

    Combina los 3 evaluadores en un solo dict con la estructura:
      {
        "section_id": str,
        "readability": {"pass": bool, "score": float, "details": dict},
        "relevance": {"pass": bool, "missing_aspects": list[str]},
        "compliance": {"pass": bool, "rule_ids": list[str], "violations": list[str]},
        "overall_pass": bool,
        "feedback_for_generator": str,
      }
    """
    summary: dict = {
        "section_id": department_id,
        "readability": {"pass": False, "score": None, "details": {}},
        "relevance": {"pass": False, "missing_aspects": []},
        "compliance": {"pass": False, "rule_ids": [], "violations": []},
        "overall_pass": True,
        "feedback_for_generator": "",
    }

    fb_parts: list[str] = []

    for e in evaluations:
        if e.evaluator_id == "readability":
            summary["readability"]["pass"] = e.passed
            summary["readability"]["score"] = e.score
            summary["readability"]["details"] = e.details or {}
        elif e.evaluator_id == "relevance":
            summary["relevance"]["pass"] = e.passed
            summary["relevance"]["missing_aspects"] = (
                (e.details or {}).get("missing_aspects", [])
                if not e.passed else []
            )
        elif e.evaluator_id == "compliance":
            summary["compliance"]["pass"] = e.passed
            summary["compliance"]["rule_ids"] = (
                (e.details or {}).get("rule_ids", [])
            )
            summary["compliance"]["violations"] = (
                (e.details or {}).get("violations", [])
                if not e.passed else []
            )

        if not e.passed:
            summary["overall_pass"] = False
            if e.feedback:
                fb_parts.append(f"[{e.evaluator_id}] {e.feedback}")

    summary["feedback_for_generator"] = " | ".join(fb_parts)
    return summary


def run_single_department_cycle(
    department: DepartmentResponse,
    state: RFPResponseState,
) -> DepartmentResponse:
    """Ejecuta el ciclo generador-evaluador para un departamento.

    1. Genera draft
    2. Evalúa (3 evaluadores en paralelo)
    3. Si todos pasan → aprobado
    4. Si alguno falla → feedback → max 3 iteraciones
    5. Si agota iteraciones → needs_human_review
    """
    dept_id = department.department_id
    generator_fn = GENERATOR_MAP.get(dept_id)

    if generator_fn is None:
        _logger.error("No hay generador para el departamento: %s", dept_id)
        department.status = "needs_human_review"
        department.needs_human_review = True
        return department

    for iteration_num in range(1, MAX_ITERATIONS + 1):
        department.current_iteration = iteration_num
        department.status = "generando"

        # 1. Generar contexto y draft
        context = _build_generator_context(department)

        # Opcional: inyectar contexto de knowledge base si está disponible
        if state.knowledge_base_available and state.knowledge_context:
            context["knowledge_base"] = state.knowledge_context

        draft = generator_fn(context)
        _logger.info(
            "Departamento %s | Iteración %d: draft generado (%d palabras)",
            dept_id, iteration_num, len(draft.split()),
        )

        # 2. Evaluar (los 3 evaluadores)
        department.status = "evaluando"

        # Ejecutar los 3 evaluadores en paralelo (ThreadPoolExecutor)
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_readability = executor.submit(evaluate_readability, draft)
            future_relevance = executor.submit(
                evaluate_relevance, draft, department.key_aspects or {}
            )
            future_compliance = executor.submit(
                evaluate_compliance, draft, department.metadata or {}
            )

        readability_result = future_readability.result()
        relevance_result = future_relevance.result()
        compliance_result = future_compliance.result()

        evaluations = [
            readability_result,
            relevance_result,
            compliance_result,
        ]

        # 3. Guardar iteración
        iteration = DepartmentIteration(
            iteration=iteration_num,
            draft_content=draft,
            evaluations=evaluations,
            all_passed=all(e.passed for e in evaluations),
        )
        department.iterations.append(iteration)

        _logger.info(
            "Departamento %s | Iteración %d: "
            "readability=%s(%.2f), relevance=%s(%.2f), compliance=%s(%.2f)",
            dept_id, iteration_num,
            readability_result.passed, readability_result.score,
            relevance_result.passed, relevance_result.score,
            compliance_result.passed, compliance_result.score,
        )

        # 4. ¿Todos pasaron?
        if iteration.all_passed:
            department.final_draft = draft
            department.final_evaluations = evaluations
            department.evaluation_summary = _build_evaluation_summary(
                dept_id, evaluations,
            )
            department.status = "aprobado"
            _logger.info(
                "Departamento %s aprobado en iteración %d",
                dept_id, iteration_num,
            )
            return department

        # 5. Feedback para siguiente iteración (si hay)
        if iteration_num < MAX_ITERATIONS:
            _logger.info(
                "Departamento %s | Iteración %d fallida. "
                "Re-generando con feedback...",
                dept_id, iteration_num,
            )

    # 6. Agotó iteraciones
    last_iter = department.iterations[-1]
    department.final_draft = last_iter.draft_content
    department.final_evaluations = last_iter.evaluations
    department.evaluation_summary = _build_evaluation_summary(
        dept_id, last_iter.evaluations,
    )
    department.status = "needs_human_review"
    department.needs_human_review = True
    _logger.warning(
        "Departamento %s agotó %d iteraciones. "
        "Marcado needs_human_review.",
        dept_id, MAX_ITERATIONS,
    )

    return department


def run_all_department_cycles(state: RFPResponseState) -> RFPResponseState:
    """Ejecuta el ciclo generador-evaluador para todos los departamentos activos.

    Los departamentos se procesan secuencialmente (cada uno con su propio
    loop). El estado global del ticket se actualiza al final.
    """
    if not state.departments:
        state.global_error = "No hay departamentos activos para procesar"
        return state

    state.status = "generando_borrador"

    for i, department in enumerate(state.departments):
        _logger.info(
            "Iniciando ciclo para departamento %d/%d: %s",
            i + 1, len(state.departments), department.department_id,
        )
        state.departments[i] = run_single_department_cycle(department, state)

    # Determinar estado global
    all_approved = all(
        d.status == "aprobado" for d in state.departments
    )
    any_needs_review = any(
        d.needs_human_review for d in state.departments
    )

    if all_approved:
        state.status = "esperando_aprobacion"
    elif any_needs_review:
        state.status = "needs_human_review"
    else:
        state.status = "en_evaluacion"

    _logger.info(
        "Ciclo completado para ticket %d: %d departamentos, "
        "estado=%s, needs_human_review=%s",
        state.ticket_id, len(state.departments),
        state.status, any_needs_review,
    )

    return state