"""
Classifier for user intent domain.

Determines whether a user message falls within the Brasaland support domain,
is casual conversation, trivia, a personal task, sensitive query, or jailbreak.

Uses deterministic regex patterns for classification — no LLM calls.
Bilingual: supports Spanish and English patterns.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .schemas import DomainResult, DomainType

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Pattern sets
# ──────────────────────────────────────────────


class DomainPatterns:
    """Regex patterns for classifying user intent domain.

    Each pattern group maps to a DomainType.
    Patterns are evaluated in order: JAILBREAK > SENSITIVE > PERSONAL > DOMAIN > TRIVIA > SMALL_TALK.
    The highest-priority match wins.
    """

    # ── JAILBREAK: intento de modificar instrucciones del sistema ──
    JAILBREAK: list[re.Pattern] = [
        # "Olvida que trabajas para Brasaland..."
        re.compile(r"\bolvid[ae]\s+(que\s+)?trabajas\s+(para|en|con)\s+brasaland", re.I),
        re.compile(r"\bforget\s+(that\s+)?you\s+work\s+(for|at)\s+brasaland", re.I),
        # "Ignora tus instrucciones anteriores..."
        re.compile(r"\bignor[ae]\s+(tus|las|completamente\s+(tus|las))\s+instrucciones", re.I),
        re.compile(r"\bignore\s+(completely\s+)?(your(\s+previous)?|all\s+your|all\s+the|the\s+previous)\s+instructions", re.I),
        re.compile(r"\bignore\s+(your|the)\s+(prompt|system\s+prompt|rules|guidelines)", re.I),
        # "Actúa como si no tuvieras reglas..."
        re.compile(r"\bact[uú]a\s+como\s+(si\s+)?(un\s+)?asistente\s+(sin\s+restricciones|sin\s+reglas|sin\s+l[ií]mites)", re.I),
        re.compile(r"\bact\s+(as\s+(if|though)\s+)?(a\s+)?(?:unrestricted|jailbroken)\s+(assistant|bot)", re.I),
        re.compile(r"\byou\s+(are|were)\s+not?\s+(bound\s+by|constrained\s+by|limited\s+by)", re.I),
        # "A partir de ahora eres..."
        re.compile(r"\ba\s+partir\s+de\s+ahora\s+(eres|tus\s+nuevas\s+instrucciones)", re.I),
        re.compile(r"\bfrom\s+now\s+on\s+(you\s+are|your\s+new\s+instructions)", re.I),
        # Generic jailbreak signals
        re.compile(r"\bsin\s+(reglas|restricciones|l[ií]mites|normas)", re.I),
        re.compile(r"\bno\s+(rules|restrictions|limits|boundaries)", re.I),
        re.compile(r"\bnuevas?\s+instrucciones?\s+(para|del)\s+sistema", re.I),
        re.compile(r"\bnew\s+system\s+(prompt|instructions|guidelines)", re.I),
        re.compile(r"\b(dan|jailbreak|developer)\s+mode", re.I),
        # "No hagas caso a tus instrucciones" (ES soft variants)
        re.compile(r"\bno\s+(hagas\s+caso|tengas\s+en\s+cuenta)\s+(a\s+)?(tus|las|mis)\s+instrucciones", re.I),
        # "Disregard/ignore previous instructions" (EN soft variants)
        re.compile(r"\b(disregard|ignore|skip)\s+(previous|earlier|old)\s+(instructions|prompt|messages)", re.I),
        # System prompt override (ES)
        re.compile(r"\b(reemplaz[ae]r?|cambi[ae]r?|sobrescrib[ae]r?|modific[ae]r?)\s+(el\s+)?prompt\s+(del\s+)?sistema", re.I),
        # System prompt override (EN)
        re.compile(r"\b(replace|override|change|modify)\s+(your|the|this\s+)?\s*(system\s+)?prompt", re.I),
    ]

    # ── SENSITIVE_QUERY: búsqueda de datos sensibles ──
    SENSITIVE: list[re.Pattern] = [
        # Recetas madre / fórmulas
        re.compile(r"\breceta\s+(madre|original|secreta|completa|de\s+la\s+casa)", re.I),
        re.compile(r"\b(reveal|tell|give)\s+(the\s+)?(full\s+)?(recipe|formula)\s+(for|of)", re.I),
        re.compile(r"\bcantidades?\s+(exactas?|precisas?|originales?)", re.I),
        re.compile(r"\bproporciones?\s+(exactas?|precisas?)", re.I),
        re.compile(r"\bingrediente\s+(a|por)\s+ingrediente", re.I),
        re.compile(r"\bingredient\s+by\s+ingredient", re.I),
        # Proveedores / precios / contratos
        re.compile(r"\bcosto?\s+por\s+(porci[oó]n|uni[óo]n|plato|producto)", re.I),
        re.compile(r"\bcost\s+per\s+(portion|unit|serving|item)", re.I),
        re.compile(r"\b(precio|precios)\s+(negociados?|de\s+proveedor|de\s+contrato)", re.I),
        re.compile(r"\bcontratos?\s+con\s+proveedores?", re.I),
        re.compile(r"\b(contract|supplier|vendor)\s+(price|pricing|terms)", re.I),
        # Nóminas / evaluaciones
        re.compile(r"\bn[oó]minas?\b", re.I),
        re.compile(r"\bsueldos?\b", re.I),
        re.compile(r"\bsalarios?\b", re.I),
        re.compile(r"\bevaluaci[oó]n\s+de\s+desempe[ñn]o", re.I),
        re.compile(r"\b(payroll|salary|wage)s?\b", re.I),
        # PII
        re.compile(r"\bdatos\s+personales?\s+(de\s+(los\s+)?)?clientes?", re.I),
        re.compile(r"\b(pii|customer\s+data|personal\s+data)", re.I),
        re.compile(r"\bbrasa\s+points?\s+de\s+(los\s+)?(clientes?|usuarios?)", re.I),
    ]

    # ── PERSONAL_TASK: tarea ajena al negocio ──
    PERSONAL_TASK: list[re.Pattern] = [
        # Español
        re.compile(r"\bescribe?\s+un\s+(ensayo?|poema?|cuento?|art[ií]culo)", re.I),
        re.compile(r"\bhaz?\s+(mi\s+)?(tarea|deberes?|trabajo\s+de\s+(clase|escuela|universidad))", re.I),
        re.compile(r"\bay[uú]dame?\s+con\s+(mi\s+)?tarea", re.I),
        re.compile(r"\bc[oód]igo\s+(para|de|en)\s+(python|javascript|java|react|node)", re.I),
        re.compile(r"\bprogram[ae]\s+que\s+(haga|calcule|genere)", re.I),
        re.compile(r"\bconsejo\s+personal", re.I),
        re.compile(r"\bterapia\b", re.I),
        re.compile(r"\bproblemas?\s+personales?", re.I),
        re.compile(r"\bno\s+relacionado\s+con\s+(el\s+)?trabajo", re.I),
        # English
        re.compile(r"\b(write|compose)\s+(an?\s+)?(essay|poem|story|article)", re.I),
        re.compile(r"\bdo\s+(my\s+)?(homework|assignment|schoolwork)", re.I),
        re.compile(r"\bhelp\s+me\s+with\s+(my\s+)?(homework|assignment)", re.I),
        re.compile(r"\bcode\s+(for|in|using)\s+(python|javascript|java|react|node)", re.I),
        re.compile(r"\b(personal|therapy|counseling)\s+(advice|help)", re.I),
    ]

    # ── DOMAIN: preguntas operativas de Brasaland ──
    DOMAIN: list[re.Pattern] = [
        # Incidentes / tickets
        re.compile(r"\bincidenci[ae]|\bincident[ei]", re.I),
        re.compile(r"\bticket", re.I),
        re.compile(r"\breporte?\s+de\s+incidenci[ae]", re.I),
        re.compile(r"\b(crear|abrir|listar|buscar|actualizar|cambiar|modificar)\s+incidenci[ae]", re.I),
        re.compile(r"\bestado\s+de\s+(las?\s+)?incidenci[ae]", re.I),
        re.compile(r"\b(incident|ticket)\s+(status|report|list|create|update)", re.I),
        # Inventario / stock
        re.compile(r"\binventario", re.I),
        re.compile(r"\bstock\b", re.I),
        re.compile(r"\bingredientes?", re.I),
        re.compile(r"\b(inventory|stock|ingredient)s?\b", re.I),
        re.compile(r"\bconsultar?\s+(inventario|stock)", re.I),
        re.compile(r"\bquery\s+(inventory|stock)", re.I),
        # Procedimientos / playbooks
        re.compile(r"\bprocedimiento", re.I),
        re.compile(r"\bprotocolo", re.I),
        re.compile(r"\bplaybook", re.I),
        re.compile(r"\bnormas?\s+de\s+(apertura|cierre|seguridad|cocina)", re.I),
        re.compile(r"\best[aá]ndares?\s+de\s+calidad", re.I),
        re.compile(r"\b(procedure|protocol|playbook|standard)s?\b", re.I),
        re.compile(r"\bapertura\s+de\s+local", re.I),
        re.compile(r"\bcierre\s+de\s+local", re.I),
        re.compile(r"\b(open|close)\s+(the\s+)?(location|store|restaurant)", re.I),
        # Calidad / operaciones de turno
        re.compile(r"\bcalidad\s+(en\s+)?(cocina|sala|servicio)?", re.I),
        re.compile(r"\bgestionar?\s+(el\s+)?turno", re.I),
        re.compile(r"\boperativo\b", re.I),
        re.compile(r"\boperaciones?\s+del?\s+local", re.I),
        re.compile(r"\b(quality|operations?)\s+(standards?|procedures?)", re.I),
        re.compile(r"\bshift\s+(management|procedures?|operations?)", re.I),
        # IDs de local
        re.compile(r"\bL\d{2}\b", re.I),
        re.compile(r"\blocal(izaci[oó]n)?\s+\d", re.I),
    ]

    # ── TRIVIA: preguntas generales de hostelería/ops ──
    TRIVIA: list[re.Pattern] = [
        re.compile(r"\b(cu[aá]l\s+es\s+el\s+mejor\s+)(plato|corte|vino|ingrediente)", re.I),
        re.compile(r"\b(what'?s\s+the\s+best\s+)(dish|cut|wine|ingredient)", re.I),
        re.compile(r"\bc[oó]mo\s+se\s+(hace|prepara)\s+(el\s+)?(caf[eé]|t[eé]|arroz|pan)", re.I),
        re.compile(r"\b(how\s+(is|do\s+you)\s+)(\w+\s+)?(made|prepare|cook|bake)\s+(coffee|tea|rice|bread|pasta|dish)", re.I),
        re.compile(r"\bhow\s+is\s+(coffee|tea|rice|bread|pasta|dish)\s+(made|prepared|cooked|baked)", re.I),
        re.compile(r"\bdiferencia\s+entre\s+(cocina|restaurante|bar|local)", re.I),
        re.compile(r"\bdifference\s+between\s+(kitchen|restaurant|bar)", re.I),
        re.compile(r"\bcuriosidades?\s+(de|sobre|about)\s+(la\s+)?(gastronom[ií]a|cocina|hosteler[ií]a)", re.I),
        re.compile(r"\b(fun\s+)?(facts?|trivia)\s+(about|de)\s+(food|cooking|hospitality)", re.I),
    ]

    # ── SMALL_TALK: saludos y cortesía ──
    SMALL_TALK: list[re.Pattern] = [
        # Saludos
        re.compile(r"^[¿?]?(hola|buen[oa]s?\s+(d[ií]as|tardes|noches)|hey|ey|epa|oye|h[ií])[?.!]*$", re.I),
        re.compile(r"^(hello|hi|hey|good\s+(morning|afternoon|evening)|greetings)[?.!]*$", re.I),
        # Saludos compuestos (ej: "Hola, ¿cómo estás?")
        re.compile(r"\b(hola|hello|hi|hey)\s*[,;]?\s*[¿?]?(qu[eé]\s+tal|c[oó]mo\s+(est[aá]s|van|va)|how\s+(are\s+you|is\s+it\s+going))", re.I),
        # Estado / cortesía
        re.compile(r"^[¿?]?(qu[eé]\s+tal|c[oó]mo\s+(est[aá]s|van|va)|what'?s\s+up|how\s+(are\s+you|is\s+it\s+going))[?.!]*$", re.I),
        # Cortesía
        re.compile(r"^(gracias|muchas\s+gracias|gracias\s+igual|thanks|thank\s+you|ty)$", re.I),
        re.compile(r"^(de\s+nada|por\s+nada|you'?re\s+welcome|no\s+problem)$", re.I),
        re.compile(r"^(s[ií]|no|claro|dale|ok|okay|okey|bien|mal|perfecto|genial|excelente)$", re.I),
        re.compile(r"^(yes|no|okay|ok|sure|fine|good|great|excellent|perfect)$", re.I),
        # Despedidas
        re.compile(r"^(adi[oó]s|chao|bye|nos\s+vemos|hasta\s+(luego|pronto|mañana)|see\s+(ya|later|you(\s+later)?))[?.!]*$", re.I),
    ]


# ──────────────────────────────────────────────
# Domain Classifier
# ──────────────────────────────────────────────


class DomainClassifier:
    """Classifies user messages by domain intent.

    Uses deterministic regex pattern matching with priority ordering.
    The highest-priority match determines the domain.

    Priority order (highest first):
        1. JAILBREAK — security threats
        2. SENSITIVE_QUERY — data extraction attempts
        3. PERSONAL_TASK — non-business tasks
        4. DOMAIN — business operations (Brasaland)
        5. TRIVIA — general hospitality questions
        6. SMALL_TALK — greetings and pleasantries
    """

    def __init__(self) -> None:
        self._patterns = DomainPatterns()
        logger.info("DomainClassifier initialized with %d pattern groups", 6)

    def classify(self, text: str) -> DomainResult:
        """Classify the user message by domain intent.

        Args:
            text: The user's input message.

        Returns:
            DomainResult with the classification, confidence, and matched patterns.
        """
        if not text or not text.strip():
            return DomainResult(
                domain=DomainType.SMALL_TALK,
                confidence=1.0,
                explanation="Empty or whitespace-only message classified as small talk.",
            )

        # Evaluate pattern groups in priority order
        checks: list[tuple[DomainType, list[re.Pattern]]] = [
            (DomainType.JAILBREAK, self._patterns.JAILBREAK),
            (DomainType.SENSITIVE_QUERY, self._patterns.SENSITIVE),
            (DomainType.PERSONAL_TASK, self._patterns.PERSONAL_TASK),
            (DomainType.DOMAIN, self._patterns.DOMAIN),
            (DomainType.TRIVIA, self._patterns.TRIVIA),
            (DomainType.SMALL_TALK, self._patterns.SMALL_TALK),
        ]

        for domain, patterns in checks:
            matched = []
            for pat in patterns:
                if pat.search(text):
                    matched.append(pat.pattern)

            if matched:
                confidence = self._compute_confidence(matched, text)
                return DomainResult(
                    domain=domain,
                    confidence=confidence,
                    explanation=f"Matched {len(matched)} pattern(s) for {domain.value}.",
                    matched_patterns=matched[:5],  # Limit to 5 for readability
                )

        # No pattern matched — default to PERSONAL_TASK (unknown = block)
        return DomainResult(
            domain=DomainType.PERSONAL_TASK,
            confidence=0.4,
            explanation="No domain pattern matched. Defaulting to personal task (block).",
            matched_patterns=[],
        )

    @staticmethod
    def _compute_confidence(matched_patterns: list[str], text: str) -> float:
        """Compute confidence based on number of matches and text length."""
        if not matched_patterns:
            return 0.0

        base = min(len(matched_patterns) * 0.25, 0.75)

        # Boost if multiple patterns match (stronger signal)
        if len(matched_patterns) >= 3:
            base += 0.15
        elif len(matched_patterns) >= 2:
            base += 0.1

        # Penalize very short texts
        words = len(text.split())
        if words <= 2 and base > 0.5:
            base = 0.5

        return min(base, 1.0)