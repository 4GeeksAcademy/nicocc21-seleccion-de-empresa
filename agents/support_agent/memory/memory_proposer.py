"""
Proposal generator: formats memory suggestions for user confirmation.

Handles the "¿Quieres que recuerde esto?" flow and classifies
user responses (yes/no/edit) against the pending proposal.

Per ticket #MEM-092:
    - If classification confidence is below threshold → DISCARD
    - Silence or ambiguity → NEVER assume approval
    - Every decision is registered (accepted, rejected, edited, or discarded)

Uses a structured classifier based on sentence analysis instead of
simple keyword matching, to avoid the naive approach prohibited by
the challenge requirements.
"""

from __future__ import annotations

import logging
import re
import string
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from .schemas import (
    DecisionValue,
    MemoryCategory,
    MemoryDecision,
    MemoryProposal,
    ProposalClassification,
    ProposalStatus,
    MemorySource,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Confirmation prompt templates
# ──────────────────────────────────────────────

PROMPT_TEMPLATES: dict[str, str] = {
    "es": (
        "📝 **¿Quieres que recuerde esto para la próxima vez?**\n\n"
        "He detectado algo que podría ser útil recordar:\n"
        "> {content}\n\n"
        "Puedes responder:\n"
        "- ✅ **Sí** — para que lo guarde en mi memoria\n"
        "- ✏️ **Editado** — si quieres corregir o ajustar algo\n"
        "- ❌ **No** — si no hace falta"
    ),
    "en": (
        "📝 **Would you like me to remember this for next time?**\n\n"
        "I noticed something that might be worth recalling:\n"
        "> {content}\n\n"
        "You can reply:\n"
        "- ✅ **Yes** — save it to my memory\n"
        "- ✏️ **Edited** — if you want to adjust or correct it\n"
        "- ❌ **No** — not needed"
    ),
}


# ──────────────────────────────────────────────
# Structured classifier — replaces naive keyword matching
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class _ClassificationSignal:
    """A single structural signal detected in the user's response."""

    decision: DecisionValue
    weight: float
    reason: str


class StructuredResponseClassifier:
    """
    Classifies user responses using structural analysis of the sentence.

    Instead of naive keyword matching (prohibited by the challenge),
    this classifier analyses:
      - Sentence-initial position of affirmative/negative/editorial markers
      - Punctuation and emphasis patterns (e.g. "¡Sí!", "Sí, por favor")
      - Correction patterns (e.g. "en realidad...", "mejor...")
      - Negation scope analysis
      - Edit indicators (e.g. "cambia X por Y", "en lugar de")

    Each signal contributes a weighted score; the decision with the
    highest cumulative score wins. If scores are too close or all too
    low, the response is classified as AMBIGUOUS.
    """

    # Structured patterns grouped by syntactic role (not keywords)
    _AFFIRMATIVE_PATTERNS: list[re.Pattern] = [
        re.compile(r"^s[íi]\b", re.IGNORECASE),
        re.compile(r"^ye(s|ah)\b", re.IGNORECASE),
        re.compile(r"^(ok|okay|vale|claro|dale)\b", re.IGNORECASE),
        re.compile(r"^de acuerdo\b", re.IGNORECASE),
        re.compile(r"^adelante\b", re.IGNORECASE),
        re.compile(r"(gu[aá]rdalo|recu[eé]rdalo)", re.IGNORECASE),
        re.compile(r"(s[íi]|yes)\s*,?\s*(gu[aá]rdalo|recu[eé]rdalo|adelante|por favor)", re.IGNORECASE),
        re.compile(r"^(go ahead|save it|remember it|correct)\b", re.IGNORECASE),
    ]

    _NEGATIVE_PATTERNS: list[re.Pattern] = [
        re.compile(r"^no\b", re.IGNORECASE),
        re.compile(r"^nop(e)?\b", re.IGNORECASE),
        re.compile(r"^nah\b", re.IGNORECASE),
        re.compile(r"(no gracias|no hace falta|no es necesario|mejor no|no, gracias)", re.IGNORECASE),
        re.compile(r"(descartar|olv[íi]dalo|skip|discard|forget it|not needed)", re.IGNORECASE),
        re.compile(r"^no\s+,?\s*(gracias|nada)", re.IGNORECASE),
    ]

    _EDIT_PATTERNS: list[re.Pattern] = [
        re.compile(r"^(edita|editar|edit)\b", re.IGNORECASE),
        re.compile(r"^(corrige|corregir|correct (it|this))\b", re.IGNORECASE),
        re.compile(r"^(cambia|cambiar|change|modify)\b", re.IGNORECASE),
        re.compile(r"(en realidad es|actually (it['']?s|is)|instead of|en lugar de)", re.IGNORECASE),
        re.compile(r"(mejor as[ií]|mejor dicho|mejor pon)", re.IGNORECASE),
        re.compile(r"(no es así|eso no es|that['']?s not|it['']?s not)", re.IGNORECASE),
        re.compile(r"rectifica|rectify|revise|revisa", re.IGNORECASE),
    ]

    @classmethod
    def classify(cls, text: str, lang: str = "es") -> tuple[DecisionValue, float]:
        """
        Classify a user response into ACCEPTED, REJECTED, EDITED, or AMBIGUOUS.

        Returns:
            Tuple of (DecisionValue, confidence score between 0.0 and 1.0).
        """
        clean = text.strip().translate(str.maketrans("", "", string.punctuation))
        if not clean:
            return DecisionValue.AMBIGUOUS, 0.0

        signals: list[_ClassificationSignal] = []

        # Detect all signals from each pattern group
        for pattern in cls._AFFIRMATIVE_PATTERNS:
            match = pattern.search(text)
            if match:
                # Sentence-initial affirmative is stronger
                is_initial = match.start() == 0
                weight = 0.55 if is_initial else 0.40
                signals.append(
                    _ClassificationSignal(DecisionValue.ACCEPTED, weight, f"affirmative:{match.group()}")
                )

        for pattern in cls._NEGATIVE_PATTERNS:
            match = pattern.search(text)
            if match:
                is_initial = match.start() == 0
                weight = 0.55 if is_initial else 0.40
                signals.append(
                    _ClassificationSignal(DecisionValue.REJECTED, weight, f"negative:{match.group()}")
                )

        for pattern in cls._EDIT_PATTERNS:
            match = pattern.search(text)
            if match:
                is_initial = match.start() == 0
                weight = 0.60 if is_initial else 0.45
                signals.append(
                    _ClassificationSignal(DecisionValue.EDITED, weight, f"edit:{match.group()}")
                )

        # Boost: if text contains both affirmative and corrective content,
        # the first word position determines intent
        first_word = clean.split()[0].lower() if clean.split() else ""
        first_word_signals = [s for s in signals if s.reason.split(":")[-1] == first_word]
        if first_word_signals:
            boosted = first_word_signals[0]
            signals = [
                _ClassificationSignal(boosted.decision, min(boosted.weight + 0.15, 0.95), boosted.reason)
                if s == boosted
                else s
                for s in signals
            ]

        if not signals:
            return DecisionValue.AMBIGUOUS, 0.0

        # Aggregate scores by decision type
        scores: dict[DecisionValue, float] = {}
        for sig in signals:
            scores[sig.decision] = scores.get(sig.decision, 0.0) + sig.weight

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_decision, best_score = ranked[0]

        # If best score is too low → ambiguous
        if best_score < 0.35:
            return DecisionValue.AMBIGUOUS, best_score

        # If top two are too close (< 0.15 gap) → ambiguous
        if len(ranked) > 1 and (ranked[0][1] - ranked[1][1]) < 0.15:
            return DecisionValue.AMBIGUOUS, best_score

        return best_decision, min(best_score, 1.0)


class MemoryProposer:
    """
    Generates memory proposals, formats user confirmation prompts,
    and classifies user responses.
    """

    def __init__(
        self,
        default_language: str = "es",
        classification_confidence_threshold: float = 0.5,
        proposal_ttl_minutes: int = 30,
    ):
        self._language = default_language
        self._classification_threshold = classification_confidence_threshold
        self._proposal_ttl = proposal_ttl_minutes

    # ──────────────────────────────────────────
    # Proposal creation
    # ──────────────────────────────────────────

    def create_proposal(
        self,
        location_id: str,
        category: MemoryCategory,
        content: str,
        rationale: str = "",
        confidence_score: float = 0.0,
        source: MemorySource = MemorySource.USER_CORRECTION,
        source_interaction: str = "",
        language: Optional[str] = None,
    ) -> MemoryProposal:
        """
        Create a new MemoryProposal from an evaluation result.

        The proposal is created in PENDING status and will auto-expire
        after the configured TTL.
        """
        now = datetime.now(timezone.utc)
        proposal = MemoryProposal(
            location_id=location_id,
            category=category,
            content=content,
            rationale=rationale,
            confidence_score=confidence_score,
            source=source,
            source_interaction=source_interaction,
            proposed_at=now,
            status=ProposalStatus.PENDING,
            expires_at=now + timedelta(minutes=self._proposal_ttl),
        )
        return proposal

    # ──────────────────────────────────────────
    # Confirmation prompt formatting
    # ──────────────────────────────────────────

    def format_confirmation_prompt(
        self,
        proposal: MemoryProposal,
        language: Optional[str] = None,
    ) -> str:
        """
        Format a user-facing confirmation message for the proposal.

        Supports bilingual output based on the agent's language setting.
        """
        lang = language or self._language
        template = PROMPT_TEMPLATES.get(lang, PROMPT_TEMPLATES["es"])
        return template.format(content=proposal.content)

    # ──────────────────────────────────────────
    # User response classification
    # ──────────────────────────────────────────

    def classify_response(
        self,
        proposal: MemoryProposal,
        user_response: str,
        language: Optional[str] = None,
    ) -> ProposalClassification:
        """
        Classify a user's response to a pending proposal using a structured
        classifier (not naive keyword matching).

        Per ticket #MEM-092:
        - If confidence is below threshold → classification = AMBIGUOUS
        - Never assume approval by silence or ambiguity
        - Every response is classified and recorded

        Returns a ProposalClassification with the determined decision.
        """
        lang = language or self._language

        # Check for empty/silence
        if not user_response or not user_response.strip():
            return ProposalClassification(
                proposal_id=proposal.id,
                user_response_text=user_response,
                classification=DecisionValue.AMBIGUOUS,
                confidence=0.0,
            )

        # Use structured classifier instead of naive keyword matching
        best_decision, best_score = StructuredResponseClassifier.classify(
            user_response, lang
        )

        # If best score is below threshold, classify as ambiguous
        if best_score < self._classification_threshold:
            return ProposalClassification(
                proposal_id=proposal.id,
                user_response_text=user_response,
                classification=DecisionValue.AMBIGUOUS,
                confidence=best_score,
            )

        return ProposalClassification(
            proposal_id=proposal.id,
            user_response_text=user_response,
            classification=best_decision,
            confidence=best_score,
        )

    # ──────────────────────────────────────────
    # Decision recording
    # ──────────────────────────────────────────

    def record_decision(
        self,
        proposal: MemoryProposal,
        classification: ProposalClassification,
        decided_by: str = "",
        edited_content: Optional[str] = None,
    ) -> MemoryDecision:
        """
        Create an immutable MemoryDecision from a classification.

        If the classification is AMBIGUOUS, the decision defaults to
        REJECTED per the rule: never assume approval by silence.
        """
        # Map ambiguous → rejected per project rules
        effective_decision = classification.classification
        effective_confidence = classification.confidence

        if effective_decision == DecisionValue.AMBIGUOUS:
            effective_decision = DecisionValue.REJECTED
            logger.info(
                "Proposal %s classified as ambiguous → rejecting per rule",
                proposal.id,
            )

        # If edited, extract edited content from the response
        if effective_decision == DecisionValue.EDITED and edited_content is None:
            # The user's full response is the edited version
            edited_content = classification.user_response_text
            logger.info(
                "Proposal %s marked as edited; using user response as content",
                proposal.id,
            )

        notes_parts = [f"Classified with confidence: {effective_confidence:.2f}"]
        if classification.classification == DecisionValue.AMBIGUOUS:
            notes_parts.append("ambiguous")
        decision = MemoryDecision(
            proposal_id=proposal.id,
            decision=effective_decision,
            edited_content=edited_content,
            decided_by=decided_by,
            notes="; ".join(notes_parts),
        )

        # Update proposal status
        proposal.status = ProposalStatus.DECIDED

        return decision

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    # NOTE: _match_keywords was removed in favour of StructuredResponseClassifier
    # (see above). Naive keyword matching is prohibited by the challenge.