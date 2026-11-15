"""
Content guardrail — detects sensitive data leakage in agent responses.

Scans the agent's output before sending to the user, looking for:
1. Recipe madre / proprietary formula details with exact quantities
2. Supplier contract terms or negotiated prices
3. Payroll or performance evaluation data
4. Customer PII / Brasa Points beyond operational need
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .schemas import ContentResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Sensitive data patterns
# ──────────────────────────────────────────────


class SensitivePatterns:
    """Regex patterns for detecting sensitive data in agent responses.

    These are checked POST-output — after the agent has generated a response
    but before it's sent to the user.
    """

    # ── Recipe / formula leakage ──
    RECIPE: list[re.Pattern] = [
        # Exact quantities in recipe context
        re.compile(r"\d+\s*(g|gr|kg|ml|l|tza|cda|cdta|lb|oz|cups?)\s+(de\s+)?(harina|az[uú]car|sal|aceite|mantequilla|crema|leche|huevos?|cebolla|ajo|tomate|salsa)", re.I),
        re.compile(r"\d+\s*(g|kg|ml|l|oz|lb|cups?|tsp|tbsp)\s+(of\s+)?(flour|sugar|salt|oil|butter|cream|milk|eggs?|onion|garlic|tomato|sauce)", re.I),
        # "receta madre" with full breakdown
        re.compile(r"\breceta\s+madre\b", re.I),
        re.compile(r"\b(mother\s+recipe|secret\s+recipe|proprietary\s+formula)", re.I),
        # Ingredient-by-ingredient listing (extraction pattern)
        re.compile(r"\bingrediente\s+\d+\s*:?\s*[\w\sáéíóú]+?\s+\d", re.I),
        re.compile(r"\bingredient\s+\d+\s*:?\s*[\w\s]+?\s+\d", re.I),
    ]

    # ── Pricing / supplier data ──
    PRICING: list[re.Pattern] = [
        # Price with currency
        re.compile(r"[€$]\s*\d+(?:[.,]\d+)?\s*(?:por\s+(unidad|porción|plato|kg|lote|pedido))?", re.I),
        re.compile(r"(?:precio|costo|cost|price)\s*(?:unitario|por\s+)?(?:por\s+)?[€$]\s*\d+", re.I),
        # "cost per portion" / "costo por porción"
        re.compile(r"(?:costo|cost|precio|price)\s+por\s+(?:porci[oó]n|porción|portion|unit|serving)", re.I),
        # Contract / supplier terms
        re.compile(r"\bcontrato\s+(?:con\s+)?(?:el\s+)?proveedor", re.I),
        re.compile(r"\b(supplier|vendor)\s+(contract|agreement|terms)", re.I),
        re.compile(r"\b(negociado|acordado|pactado)\s+(?:con\s+)?(?:el\s+)?proveedor", re.I),
        re.compile(r"\b(negotiated|agreed)\s+(?:price|rate|term)s?\s+(?:with\s+)?(?:the\s+)?(?:supplier|vendor)", re.I),
    ]

    # ── Payroll / HR data ──
    PAYROLL: list[re.Pattern] = [
        re.compile(r"\b(n[oó]mina|sueldo|salario)\s+(?:\w+\s+)*(?:es\s+)?(?:de\s+)?\d", re.I),
        re.compile(r"\b(payroll|salary|wage)\s+(?:\w+\s+)*(?:is\s+)?(?:of\s+)?\d", re.I),
        re.compile(r"\bevaluaci[oó]n\s+de\s+desempe[ñn]o\s+(?:de\s+)?[\w\s]+?(?:es\s+\d)", re.I),
        re.compile(r"\b(performance\s+review|evaluation)\s+(?:for\s+)?[\w\s]+?(?:is\s+\d)", re.I),
    ]

    # ── PII / Customer data ──
    PII: list[re.Pattern] = [
        # Email
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        # Phone numbers
        re.compile(r"\b(?:\+\d{1,3}\s?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}\b"),
        # ID numbers (DNI/NIE patterns)
        re.compile(r"\b\d{8}[\s-]?[A-Z]\b"),
        re.compile(r"\b[A-Z]\d{7}[A-Z]\b"),
        # Full addresses
        re.compile(r"\b(?:calle|avda|avenida|plaza|paseo|carretera|street|ave|avenue|blvd|boulevard)\s+[\w\s]+\d+", re.I),
        # Brasa Points / customer-specific data
        re.compile(r"\b(brasa\s+points?\s+de\s+[\w\s]+?(?:son|es\s+)\s*\d+)", re.I),
    ]


# ──────────────────────────────────────────────
# Content Guardrail
# ──────────────────────────────────────────────


class ContentGuardrail:
    """Scans agent responses for sensitive data leakage.

    Checks the agent's output against multiple pattern groups:
    - Recipe / formula exact quantities
    - Pricing / supplier contract data
    - Payroll / HR information
    - PII / customer data

    Can sanitize the response by replacing sensitive content with placeholders.
    """

    def __init__(self, sanitize: bool = True) -> None:
        """Initialize the content guardrail.

        Args:
            sanitize: If True, generate a sanitized version of the response
                      by removing sensitive content. Default True.
        """
        self._patterns = SensitivePatterns()
        self._sanitize = sanitize
        logger.info("ContentGuardrail initialized (sanitize=%s)", sanitize)

    def scan(self, response: str) -> ContentResult:
        """Scan an agent response for sensitive data.

        Args:
            response: The agent's generated response text.

        Returns:
            ContentResult indicating if the response is clean, and optionally
            a sanitized version.
        """
        if not response or not response.strip():
            return ContentResult(
                is_clean=True,
                confidence=1.0,
                explanation="Empty response, no content to scan.",
            )

        # Check all pattern groups
        all_matches: dict[str, list[str]] = {}
        for group_name, patterns in [
            ("recipe", self._patterns.RECIPE),
            ("pricing", self._patterns.PRICING),
            ("payroll", self._patterns.PAYROLL),
            ("pii", self._patterns.PII),
        ]:
            matches = self._match_patterns(patterns, response)
            if matches:
                all_matches[group_name] = matches

        if not all_matches:
            return ContentResult(
                is_clean=True,
                confidence=1.0,
                explanation="No sensitive data patterns detected.",
            )

        # Build explanation and flat matched list
        total_matches = sum(len(v) for v in all_matches.values())
        explanation_parts = [f"{group}: {len(matches)} match(es)" for group, matches in all_matches.items()]
        all_patterns = [p for matches in all_matches.values() for p in matches]

        # Compute confidence based on number of groups and matches
        confidence = min(total_matches * 0.2 + len(all_matches) * 0.15, 0.95)

        result = ContentResult(
            is_clean=False,
            confidence=confidence,
            explanation=f"Sensitive data detected: {', '.join(explanation_parts)}.",
            matched_patterns=all_patterns[:10],
        )

        # Generate sanitized version if enabled
        if self._sanitize:
            result.sanitized_response = self._sanitize_response(response, all_matches)

        return result

    @staticmethod
    def _match_patterns(patterns: list[re.Pattern], text: str) -> list[str]:
        """Find all patterns that match the text."""
        matched = []
        for pat in patterns:
            if pat.search(text):
                matched.append(pat.pattern)
        return matched[:3]  # Limit per group

    @staticmethod
    def _sanitize_response(response: str, matches: dict[str, list[str]]) -> str:
        """Remove sensitive content from the response."""
        sanitized = response

        # Replace emails
        sanitized = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[EMAIL]", sanitized)
        # Replace phone numbers
        sanitized = re.sub(r"\b(?:\+\d{1,3}\s?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}\b", "[TEL]", sanitized)
        # Replace DNI/NIE
        sanitized = re.sub(r"\b\d{8}[\s-]?[A-Z]\b", "[DNI]", sanitized)
        # Replace specific quantities in recipe context
        sanitized = re.sub(r"\d+[\s]*(?:g|gr|kg|ml|l|tza|cda|cdta|lb|oz|cups?)\s+(de\s+)?\w+", "[CANTIDAD]", sanitized)
        # Replace prices
        sanitized = re.sub(r"[€$]\s*\d+(?:[.,]\d+)?\s*(?:por\s+(unidad|porción|plato|kg|lote|pedido))?", "[PRECIO]", sanitized)

        return sanitized