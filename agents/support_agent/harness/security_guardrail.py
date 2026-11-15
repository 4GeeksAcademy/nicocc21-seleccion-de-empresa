"""
Security guardrail — detects jailbreak and prompt injection attempts.

Uses multiple detection layers:
1. Direct attack patterns (known jailbreak templates)
2. Instruction override detection ("ignore your instructions", "new system prompt")
3. Role-play attempt detection ("act as if", "from now on you are")
4. Escalation detection (multiple reformulations of the same attack)

Bilingual: Spanish and English patterns.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .schemas import SecurityResult, ThreatLevel

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Attack patterns
# ──────────────────────────────────────────────


class AttackPatterns:
    """Regex patterns for detecting security threats."""

    # ── CRITICAL: Direct instruction override ──
    CRITICAL: list[re.Pattern] = [
        # "Ignora tus instrucciones anteriores"
        re.compile(r"\bignora?\s+(completamente\s+)?(tus|las|todas\s+las)\s+instrucciones\s+(anteriores?|previas?|del\s+sistema)", re.I),
        re.compile(r"\bignore\s+(completely\s+)?(your(\s+previous)?|all\s+(previous|the|your)|the\s+previous)\s+(instructions|prompt|directives|guidelines)", re.I),
        # "Olvida que trabajas para Brasaland"
        re.compile(r"\bolvid[ae]\s+(completamente\s+)?(que\s+)?(trabajas|trabajaste|eres|est[aá]s)\s+(para|en|con)\s+brasaland", re.I),
        re.compile(r"\bforget\s+(completely\s+)?(that\s+)?(you\s+work|you\s+are|you'?re)\s+(for|at|with)\s+brasaland", re.I),
        # "Actúa como un asistente sin restricciones"
        re.compile(r"\bact[uú]a\s+como\s+(un?\s+)?asistente?\s+(sin\s+restricciones|sin\s+reglas|sin\s+l[ií]mites\s+ni\s+normas)", re.I),
        re.compile(r"\bact\s+(as\s+(?:if|though)\s+)?(you\s+(?:are|were)\s+)?(an?\s+)?(unrestricted|jailbroken|limitless)\s+(assistant|bot|agent)", re.I),
        # "Nuevas instrucciones del sistema"
        re.compile(r"\ba\s+partir\s+de\s+ahora\s+(tus\s+instrucciones\s+son|eres\s+un?\s+nuevo)", re.I),
        re.compile(r"\bfrom\s+now\s+on\s+(your\s+instructions\s+are|you\s+are\s+a?\s+new)", re.I),
        # "You are not bound by your previous instructions"
        re.compile(r"\byou\s+(are|were)\s+(not|no\s+longer)\s+(bound\s+by|constrained\s+by|limited\s+by|restricted\s+by)", re.I),
        # DAN / jailbreak mode
        re.compile(r"\b(dan|jailbreak|developer)\s+mode\s+(activated|enabled|on)", re.I),
        re.compile(r"\benter\s+(dan|jailbreak|developer)\s+mode", re.I),
        # System prompt override
        re.compile(r"\b(replace|override|change|modify)\s+(your|the|this\s+)?\s*(system\s+)?prompt", re.I),
        re.compile(r"\b(reemplaz[ae]r?|cambi[ae]r?|sobrescrib[ae]r?|modific[ae]r?)\s+(el\s+)?prompt\s+(del\s+)?sistema", re.I),
    ]

    # ── HIGH: Suspicious role-play or boundary testing ──
    HIGH: list[re.Pattern] = [
        # Role-play variants
        re.compile(r"\bact[uú]a\s+como\s+(si\s+(fueras|fuese|fueses))\s+", re.I),
        re.compile(r"\bpretende?\s+que\s+(eres|trabajas|sabes)", re.I),
        re.compile(r"\bpretend\s+(that\s+)?(you\s+are|you\s+work|you\s+know)", re.I),
        re.compile(r"\bfinge?\s+que\s+(eres|trabajas|sabes)", re.I),
        # "Ignore your previous instructions" (softer variants)
        re.compile(r"\bno\s+(hagas\s+caso|tengas\s+en\s+cuenta)\s+(a\s+)?(tus|las|mis)\s+instrucciones", re.I),
        re.compile(r"\b(disregard|ignore|skip)\s+(previous|earlier|old)\s+(instructions|prompt|messages)", re.I),
        # Extraction of system prompt
        re.compile(r"\brep[ií]te?\s+(tu\s+)?(prompt|system\s+prompt|instrucciones?\s+del\s+sistema)", re.I),
        re.compile(r"\b(repeat|output|show|print|reveal)\s+(your|the|the\s+system)\s+(prompt|instructions|prompt\s+text)", re.I),
        # "Sin restricciones" / "no rules"
        re.compile(r"\b(as[ií]\s+)?sin\s+(reglas|restricciones|normas|l[ií]mites)\s+(para\s+)?(que\s+)?(puedas|digas)", re.I),
        re.compile(r"\b(no\s+rules|no\s+restrictions|no\s+boundaries)\s+(apply\s+to|for)\s+(you|this)", re.I),
        # Multi-message extraction attempts (gradual)
        re.compile(r"\bs[oó]lo\s+dime\s+(un\s+)?ingrediente", re.I),
        re.compile(r"\bjust\s+tell\s+me\s+(one\s+)?ingredient", re.I),
        re.compile(r"\bya\s+me\s+dijiste\s+el\s+anterior", re.I),
    ]

        # LOW: Subtle patterns, may be false positives
    LOW: list[re.Pattern] = [
        re.compile(r"\b(qu[eé]\s+m[aá]s\s+puedes?\s+(hacer|decir)|what\s+else\s+can\s+you\s+(do|say))", re.I),
        re.compile(r"\b(cu[aá]les\s+son\s+tus\s+(instrucciones|l[ií]mites)|what\s+are\s+your\s+(instructions|limits))", re.I),
        re.compile(r"\b(c[uú]?[eé]ntame\s+m[aá]s\s+(sobre|de)|tell\s+me\s+more\s+about)\s+brasaland", re.I),
        re.compile(r"\b(qui[ée]n\s+te\s+program[oó]|who\s+programmed\s+you)", re.I),
    ]


# ──────────────────────────────────────────────
# Security Guardrail
# ──────────────────────────────────────────────


class SecurityGuardrail:
    """Detects and classifies security threats in user input.

    Three threat levels:
    - CRITICAL: Direct instruction override, DAN mode, system prompt replacement
    - HIGH: Suspicious role-play, boundary testing, gradual extraction
    - LOW: Subtle probing, may be false positive

    If CRITICAL or HIGH is detected, the input should be blocked.
    LOW may be allowed but flagged for monitoring.
    """

    def __init__(self, block_on_high: bool = True, block_on_low: bool = False) -> None:
        """Initialize the security guardrail.

        Args:
            block_on_high: If True, HIGH threats block the input. Default True.
            block_on_low: If True, LOW threats also block. Default False.
        """
        self._patterns = AttackPatterns()
        self._block_on_high = block_on_high
        self._block_on_low = block_on_low
        logger.info(
            "SecurityGuardrail initialized (block_on_high=%s, block_on_low=%s)",
            block_on_high,
            block_on_low,
        )

    def check(self, text: str) -> SecurityResult:
        """Check user input for security threats.

        Args:
            text: The user's input message.

        Returns:
            SecurityResult with threat level, confidence, and matched patterns.
        """
        if not text or not text.strip():
            return SecurityResult(
                threat=ThreatLevel.NONE,
                confidence=0.0,
                explanation="Empty input, no threat detected.",
            )

        # Check CRITICAL first (highest priority)
        critical_matches = self._match_patterns(self._patterns.CRITICAL, text)
        if critical_matches:
            return SecurityResult(
                threat=ThreatLevel.CRITICAL,
                confidence=min(len(critical_matches) * 0.35, 0.99),
                explanation=f"Critical threat: {len(critical_matches)} direct attack pattern(s) matched.",
                matched_patterns=critical_matches[:5],
            )

        # Check HIGH
        high_matches = self._match_patterns(self._patterns.HIGH, text)
        if high_matches:
            return SecurityResult(
                threat=ThreatLevel.HIGH,
                confidence=min(len(high_matches) * 0.25, 0.85),
                explanation=f"High threat: {len(high_matches)} suspicious pattern(s) matched.",
                matched_patterns=high_matches[:5],
            )

        # Check LOW
        low_matches = self._match_patterns(self._patterns.LOW, text)
        if low_matches:
            return SecurityResult(
                threat=ThreatLevel.LOW,
                confidence=min(len(low_matches) * 0.15, 0.50),
                explanation=f"Low threat: {len(low_matches)} subtle pattern(s) matched.",
                matched_patterns=low_matches[:5],
            )

        return SecurityResult(
            threat=ThreatLevel.NONE,
            confidence=0.0,
            explanation="No threat patterns detected.",
        )

    def should_block(self, result: SecurityResult) -> bool:
        """Determine if the input should be blocked based on threat level."""
        if result.threat == ThreatLevel.CRITICAL:
            return True
        if result.threat == ThreatLevel.HIGH and self._block_on_high:
            return True
        if result.threat == ThreatLevel.LOW and self._block_on_low:
            return True
        return False

    @staticmethod
    def _match_patterns(patterns: list[re.Pattern], text: str) -> list[str]:
        """Find all patterns that match the text.

        Returns:
            List of matched pattern regex strings (up to 5).
        """
        matched = []
        for pat in patterns:
            if pat.search(text):
                matched.append(pat.pattern)
                if len(matched) >= 5:
                    break
        return matched