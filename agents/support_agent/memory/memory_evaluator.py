"""
Auto-evaluator: determines whether an interaction is worth remembering.

Uses the checklist from the company briefing to decide if a piece
of information should be proposed for memory storage.

Evaluation rules (from company briefing):
    ✅ Correcciones operativas recurrentes → PROPOSE
    ✅ Contexto de escalación resuelta → PROPOSE
    ✅ Preferencias de comunicación → PROPOSE
    ❌ Datos personales de clientes → REJECT
    ❌ Nómina/compensación → REJECT
    ❌ Conversaciones puntuales sin patrón → REJECT
"""

from __future__ import annotations

import re
from typing import Optional

from .schemas import (
    EvaluationResult,
    MemoryCategory,
    MemorySource,
)


# ──────────────────────────────────────────────
# Pattern definitions
# ──────────────────────────────────────────────


class SensitivityPatterns:
    """Patterns that indicate information should NEVER be memorised."""

    # Personal data / CRM data
    PERSONAL_DATA = re.compile(
        r"\b(dni|nif|pasaporte|cc\b|identificaci.n|tel.fono|"
        r"correo|email|direcci.n|direccion|"
        r"tarjeta|cuenta\s+bancaria|iban)\b",
        re.IGNORECASE,
    )

    # Payroll / compensation
    PAYROLL = re.compile(
        r"\b(n.mina|salario|sueldo|compensaci.n|compensacion|"
        r"bono|bonificaci.n|bonificacion|pago\s+mensual|"
        r"ingresos\s+personales)\b",
        re.IGNORECASE,
    )

    # One-shot / non-repeatable
    ONE_SHOT = re.compile(
        r"\b(gracias\s*(por|eso)|resuelve\s+mi\s+duda|"
        r"traducir\s+esto\s+al|thanks|that's\s+all|"
        r"nada\s+m.s|no\s+necesito\s+nada\s+m.s)\b",
        re.IGNORECASE,
    )


class PositivePatterns:
    """Patterns that indicate information IS worth remembering."""

    # Operational corrections (schedules, delivery days, etc.)
    SCHEDULE_CORRECTION = re.compile(
        r"\b(cierra|abre|horario|hora\s+de|"
        r"closes?|opens?|schedule|"
        r"entrega(\s+(los|el\s+))?|"
        r"reparto|"
        r"abrimos|cerramos|"
        r"a\s+las\s+\d{1,2}(:\d{2})?\s*(am|pm|a\.\s*m\.|p\.\s*m\.)?|"
        r"\d{1,2}(:\d{2})?\s*(pm|am)\b)\b",
        re.IGNORECASE,
    )

    # Supplier corrections
    SUPPLIER_CORRECTION = re.compile(
        r"\b(proveedor|distribuidor|proveedora|"
        r"entrega\s+(los|lunes|martes|mi.rcoles|jueves|viernes|"
        r"s.bado|domingo)|"
        r"carne|vegetales|l.cteos|pan|bebidas|"
        r"no\s+(es|son|entrega)\s+los\s+|"
        r"en\s+realidad\s+es\s+el\s+|"
        r"espera\s+es\s+el\s+|"
        r"es\s+el\s+(lunes|martes|mi.rcoles|jueves|viernes|"
        r"s.bado|domingo)\s+no\s+el\s+)\b",
        re.IGNORECASE,
    )

    # Hours / closing time corrections
    HOURS_CORRECTION = re.compile(
        r"\b(cierra\s+(a\s+las|a\s+la|a\s+)|"
        r"abre\s+(a\s+las|a\s+la)|"
        r"hasta\s+las\s+|"
        r"\d{1,2}(:\d{2})?\s*(pm|a\.\s*m\.|p\.\s*m\.|am|a\.m\.|p\.m\.)\b|"
        r"medianoche|mediod.a|"
        r"los\s+(viernes|s.bados|domingos|fines\s+de\s+semana)\s+(cierra|abre)|"
        r"cambio\s+de\s+horario|nuevo\s+horario|"
        r"ahora\s+(cierra|abre))\b",
        re.IGNORECASE,
    )

    # Known incidents / escalations
    INCIDENT_PATTERN = re.compile(
        r"\b(alerta|apag.n|corte\s+(de\s+)?luz|"
        r"problema\s+conocido|ya\s+pas.|"
        r"escalaci.n|escalacion|"
        r"incidente|error\s+del\s+(pos|sistema)|"
        r"no\s+es\s+un\s+error\s+del|"
        r"ya\s+ocurri.|"
        r"mismo\s+problema|otra\s+vez\s+lo\s+mismo)\b",
        re.IGNORECASE,
    )

    # User preferences
    PREFERENCE_PATTERN = re.compile(
        r"\b(prefiero|preferir.a|quisiera\s+que|"
        r"me\s+gustar.a\s+(recibir|que|ver)|"
        r"formato|reporte\s+en|"
        r"m.andame|env.ame|"
        r"siempre\s+(pido|suelo|hago)|"
        r"acostumbro|normalmente\s+lo\s+hago|"
        r"como\s+siempre)\b",
        re.IGNORECASE,
    )


# ──────────────────────────────────────────────
# Evaluator
# ──────────────────────────────────────────────


class MemoryEvaluator:
    """
    Evaluates whether an interaction fragment is worth remembering.

    Uses rule-based pattern matching aligned with the company briefing.
    Returns an EvaluationResult with category, confidence, and rationale.
    """

    def __init__(self, confidence_threshold: float = 0.4):
        self._threshold = confidence_threshold

    def evaluate(
        self,
        text: str,
        location_id: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Evaluate a piece of interaction text.

        Args:
            text: The text to evaluate (user message + agent response).
            location_id: Optional location context for richer evaluation.

        Returns:
            EvaluationResult with should_propose, category, confidence, rationale.
        """
        if not text or not text.strip():
            return EvaluationResult(
                should_propose=False,
                rationale="Empty or whitespace-only text.",
            )

        # ── Step 1: Check sensitive/rejection patterns ──
        rejection = self._check_rejection_patterns(text)
        if rejection:
            return rejection

        # ── Step 2: Check positive patterns ──
        positive = self._check_positive_patterns(text, location_id)
        if positive and positive.confidence_score >= self._threshold:
            return positive

        # ── Step 3: If nothing matched, don't propose ──
        return EvaluationResult(
            should_propose=False,
            rationale="No memorable pattern detected in the interaction.",
            source_text=text[:200],
        )

    # ──────────────────────────────────────────
    # Rejection logic
    # ──────────────────────────────────────────

    def _check_rejection_patterns(self, text: str) -> Optional[EvaluationResult]:
        """
        Check if the text matches any NEVER-memorise pattern.
        Returns an EvaluationResult with should_propose=False if matched.
        """
        # Personal data → reject
        if SensitivityPatterns.PERSONAL_DATA.search(text):
            return EvaluationResult(
                should_propose=False,
                rationale="Contains personal/CRM data — never memorise per company briefing.",
                source_text=text[:200],
            )

        # Payroll / compensation → reject
        if SensitivityPatterns.PAYROLL.search(text):
            return EvaluationResult(
                should_propose=False,
                rationale="Contains payroll or compensation data — never memorise per company briefing.",
                source_text=text[:200],
            )

        # One-shot / non-repeatable → reject
        if SensitivityPatterns.ONE_SHOT.search(text):
            return EvaluationResult(
                should_propose=False,
                rationale="One-shot interaction or conversation closure — no pattern to remember.",
                source_text=text[:200],
            )

        return None

    # ──────────────────────────────────────────
    # Positive evaluation logic
    # ──────────────────────────────────────────

    def _check_positive_patterns(
        self,
        text: str,
        location_id: Optional[str] = None,
    ) -> Optional[EvaluationResult]:
        """
        Check if the text matches any WORTH-remembering pattern.
        Returns the strongest match by confidence score.
        
        When multiple patterns have equal confidence, prefers more
        semantically specific categories (preferences > incidents > 
        operational details).
        """
        candidates: list[EvaluationResult] = []

        # ── Communication preferences (checked first — when preferences
        #    overlap with schedules, user intent is usually the preference) ──
        if PositivePatterns.PREFERENCE_PATTERN.search(text):
            score = self._compute_confidence(text, PositivePatterns.PREFERENCE_PATTERN)
            candidates.append(
                EvaluationResult(
                    should_propose=True,
                    category=MemoryCategory.COMMUNICATION_PREFERENCES,
                    confidence_score=score,
                    rationale="Detected user communication or format preference.",
                    source_text=text[:200],
                )
            )

        # ── Operational corrections (schedules/days) ──
        if PositivePatterns.SCHEDULE_CORRECTION.search(text):
            score = self._compute_confidence(text, PositivePatterns.SCHEDULE_CORRECTION)
            candidates.append(
                EvaluationResult(
                    should_propose=True,
                    category=MemoryCategory.SCHEDULES,
                    confidence_score=score,
                    rationale="Detected schedule or operating-hours correction.",
                    source_text=text[:200],
                )
            )

        # ── Supplier corrections ──
        if PositivePatterns.SUPPLIER_CORRECTION.search(text):
            score = self._compute_confidence(text, PositivePatterns.SUPPLIER_CORRECTION)
            candidates.append(
                EvaluationResult(
                    should_propose=True,
                    category=MemoryCategory.SUPPLIERS,
                    confidence_score=score,
                    rationale="Detected supplier or delivery-day correction.",
                    source_text=text[:200],
                )
            )

        # ── Hours / closing time corrections ──
        if PositivePatterns.HOURS_CORRECTION.search(text):
            score = self._compute_confidence(text, PositivePatterns.HOURS_CORRECTION)
            candidates.append(
                EvaluationResult(
                    should_propose=True,
                    category=MemoryCategory.SCHEDULES,
                    confidence_score=score,
                    rationale="Detected opening/closing hours correction.",
                    source_text=text[:200],
                )
            )

        # ── Known incidents / escalations ──
        if PositivePatterns.INCIDENT_PATTERN.search(text):
            score = self._compute_confidence(text, PositivePatterns.INCIDENT_PATTERN)
            candidates.append(
                EvaluationResult(
                    should_propose=True,
                    category=MemoryCategory.KNOWN_INCIDENTS,
                    confidence_score=score,
                    rationale="Detected escalation or known incident context.",
                    source_text=text[:200],
                )
            )

        if not candidates:
            return None

        # Return the candidate with the highest confidence
        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates[0]

    # ──────────────────────────────────────────
    # Confidence computation
    # ──────────────────────────────────────────

    def _compute_confidence(self, text: str, pattern: re.Pattern) -> float:
        """
        Compute a confidence score based on match density.

        More matches → higher confidence. Caps at 0.95 to leave room
        for human override.
        """
        matches = list(pattern.finditer(text))
        if not matches:
            return 0.0

        # Base: 0.4 for a single match
        base = 0.4
        # Boost for multiple distinct matches (use full match text)
        unique_matches = len(set(m.group(0).lower().strip() for m in matches if m.group(0).strip()))
        boost = min(unique_matches * 0.15, 0.55)  # max boost 0.55

        return min(base + boost, 0.95)

    @property
    def threshold(self) -> float:
        return self._threshold