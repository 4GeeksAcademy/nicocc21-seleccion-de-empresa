"""
Proposal generator: formats memory suggestions for user confirmation.

Handles the "¿Quieres que recuerde esto?" flow and classifies
user responses (yes/no/edit) against the pending proposal.

Per ticket #MEM-092:
    - If classification confidence is below threshold → DISCARD
    - Silence or ambiguity → NEVER assume approval
    - Every decision is registered (accepted, rejected, edited, or discarded)
"""

from __future__ import annotations

import logging
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
# Response classification patterns
# ──────────────────────────────────────────────

# Simple keyword-based classification for the MVP.
# In production this could be an LLM call.
ACCEPT_KEYWORDS: dict[str, set[str]] = {
    "es": {"sí", "si", "yes", "vale", "ok", "de acuerdo", "adelante", "guárdalo", "recuérdalo", "claro", "dale"},
    "en": {"yes", "yeah", "sure", "ok", "okay", "go ahead", "remember it", "save it", "correct"},
}

REJECT_KEYWORDS: dict[str, set[str]] = {
    "es": {"no", "nop", "nope", "no gracias", "no hace falta", "no es necesario", "mejor no", "descartar", "olvídalo"},
    "en": {"no", "nope", "nah", "no thanks", "not needed", "discard", "forget it", "skip"},
}

EDIT_KEYWORDS: dict[str, set[str]] = {
    "es": {"edita", "editar", "corrige", "corregir", "cambia", "cambiar", "modifica", "modificar", "en realidad es", "mejor así", "en lugar de"},
    "en": {"edit", "correct", "change", "modify", "actually it's", "instead of", "revise"},
}


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
        Classify a user's response to a pending proposal.

        Per ticket #MEM-092:
        - If confidence is below threshold → classification = AMBIGUOUS
        - Never assume approval by silence or ambiguity
        - Every response is classified and recorded

        Returns a ProposalClassification with the determined decision.
        """
        lang = language or self._language
        response_lower = user_response.strip().lower()

        # Check for empty/silence
        if not response_lower:
            return ProposalClassification(
                proposal_id=proposal.id,
                user_response_text=user_response,
                classification=DecisionValue.AMBIGUOUS,
                confidence=0.0,
            )

        # Check for accept keywords
        accept_score = self._match_keywords(
            response_lower, ACCEPT_KEYWORDS.get(lang, ACCEPT_KEYWORDS["es"])
        )
        reject_score = self._match_keywords(
            response_lower, REJECT_KEYWORDS.get(lang, REJECT_KEYWORDS["es"])
        )
        edit_score = self._match_keywords(
            response_lower, EDIT_KEYWORDS.get(lang, EDIT_KEYWORDS["es"])
        )

        # Determine best classification
        scores = [
            (DecisionValue.ACCEPTED, accept_score),
            (DecisionValue.REJECTED, reject_score),
            (DecisionValue.EDITED, edit_score),
        ]
        scores.sort(key=lambda x: x[1], reverse=True)

        best_decision, best_score = scores[0]

        # If best score is below threshold, classify as ambiguous
        if best_score < self._classification_threshold:
            return ProposalClassification(
                proposal_id=proposal.id,
                user_response_text=user_response,
                classification=DecisionValue.AMBIGUOUS,
                confidence=best_score,
            )

        # If there's a near-tie between top two, mark ambiguous
        if len(scores) > 1 and abs(scores[0][1] - scores[1][1]) < 0.2:
            return ProposalClassification(
                proposal_id=proposal.id,
                user_response_text=user_response,
                classification=DecisionValue.AMBIGUOUS,
                confidence=best_score,
                # Note: ambiguous because the top two scores are too close
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

    def _match_keywords(self, text: str, keywords: set[str]) -> float:
        """
        Match user response against a set of keywords.

        Returns a confidence score between 0.0 and 1.0 based on
        the proportion of keywords found and their position weight.
        """
        if not text or not keywords:
            return 0.0

        # Strip common punctuation for word matching
        import string
        clean = text.translate(str.maketrans('', '', string.punctuation))

        matched = 0
        for kw in keywords:
            if kw in text:
                matched += 1

        if matched == 0:
            return 0.0

        # Base score: proportion of keywords matched
        base = matched / len(keywords)
        # Boost if the first word is a keyword (strong signal)
        first_word = clean.split()[0].lower() if clean.split() else ""
        if first_word in keywords:
            base += 0.5

        return min(base, 1.0)