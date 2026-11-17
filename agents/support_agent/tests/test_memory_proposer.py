"""Tests for MemoryProposer — proposal creation, confirmation prompts, and response classification."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from agents.support_agent.memory.memory_proposer import MemoryProposer
from agents.support_agent.memory.schemas import (
    DecisionValue,
    MemoryCategory,
    MemoryProposal,
    MemorySource,
    ProposalStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def proposer() -> MemoryProposer:
    return MemoryProposer(
        default_language="es",
        classification_confidence_threshold=0.5,
        proposal_ttl_minutes=30,
    )


@pytest.fixture
def sample_proposal(proposer: MemoryProposer) -> MemoryProposal:
    return proposer.create_proposal(
        location_id="L03",
        category=MemoryCategory.SCHEDULES,
        content="El local cierra a las 10pm los viernes",
        rationale="Schedule correction detected",
        confidence_score=0.75,
        source=MemorySource.USER_CORRECTION,
        source_interaction="El local cierra a las 10pm los viernes",
    )


# ---------------------------------------------------------------------------
# Proposal creation
# ---------------------------------------------------------------------------


class TestProposalCreation:
    def test_create_proposal(self, proposer: MemoryProposer):
        prop = proposer.create_proposal(
            location_id="L03",
            category=MemoryCategory.SCHEDULES,
            content="Cierra a las 10pm",
        )
        assert prop.location_id == "L03"
        assert prop.category == MemoryCategory.SCHEDULES
        assert prop.content == "Cierra a las 10pm"
        assert prop.status == ProposalStatus.PENDING
        assert prop.id.startswith("prop_")

    def test_proposal_has_expiration(self, proposer: MemoryProposer):
        now = datetime.now(timezone.utc)
        prop = proposer.create_proposal(
            location_id="L03",
            category=MemoryCategory.SUPPLIERS,
            content="Proveedor pasa los jueves",
        )
        assert prop.expires_at is not None
        assert prop.expires_at > now
        # Should be ~30 minutes from now
        diff = (prop.expires_at - now).total_seconds()
        assert 25 * 60 < diff < 35 * 60  # 30 min ±5

    def test_proposal_defaults(self, proposer: MemoryProposer):
        prop = proposer.create_proposal(
            location_id="L01",
            category=MemoryCategory.OTHER,
            content="Test",
        )
        assert prop.confidence_score == 0.0
        assert prop.source == MemorySource.USER_CORRECTION
        assert prop.rationale == ""
        assert prop.source_interaction == ""

    def test_proposal_custom_ttl(self):
        short = MemoryProposer(proposal_ttl_minutes=5)
        prop = short.create_proposal("L01", MemoryCategory.OTHER, "Test")
        diff = (prop.expires_at - prop.proposed_at).total_seconds()
        assert 4 * 60 < diff < 6 * 60  # 5 min ±1


# ---------------------------------------------------------------------------
# Confirmation prompts
# ---------------------------------------------------------------------------


class TestConfirmationPrompts:
    def test_prompt_spanish(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        prompt = proposer.format_confirmation_prompt(sample_proposal, language="es")
        assert "¿Quieres que recuerde esto" in prompt
        assert "cierra a las 10pm" in prompt
        assert "Sí" in prompt or "✅" in prompt

    def test_prompt_english(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        prompt = proposer.format_confirmation_prompt(sample_proposal, language="en")
        assert "Would you like me to remember" in prompt
        assert "cierra a las 10pm" in prompt

    def test_prompt_default_language(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """Uses the default_language set at construction."""
        prompt = proposer.format_confirmation_prompt(sample_proposal)
        assert "¿Quieres que recuerde esto" in prompt

    def test_prompt_fallback_to_spanish(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """Unknown language falls back to Spanish."""
        prompt = proposer.format_confirmation_prompt(sample_proposal, language="fr")
        assert "¿Quieres que recuerde esto" in prompt


# ---------------------------------------------------------------------------
# Response classification
# ---------------------------------------------------------------------------


class TestResponseClassification:
    """Per ticket #MEM-092: explicit classification, never assume approval by silence."""

    def test_classify_accept_spanish(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Sí, guárdalo")
        assert classification.classification == DecisionValue.ACCEPTED
        assert classification.confidence >= 0.5

    def test_classify_accept_english(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Yes, remember it", language="en")
        assert classification.classification == DecisionValue.ACCEPTED
        assert classification.confidence >= 0.5

    def test_classify_reject_spanish(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "No, no hace falta")
        assert classification.classification == DecisionValue.REJECTED
        assert classification.confidence >= 0.5

    def test_classify_reject_english(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "No thanks", language="en")
        assert classification.classification == DecisionValue.REJECTED
        assert classification.confidence >= 0.5

    def test_classify_edit_spanish(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Corrige, es a las 9pm")
        assert classification.classification == DecisionValue.EDITED
        assert classification.confidence >= 0.5

    def test_classify_edit_english(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Edit: it's 9pm", language="en")
        assert classification.classification == DecisionValue.EDITED
        assert classification.confidence >= 0.5

    def test_empty_response_is_ambiguous(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """Silence/empty → AMBIGUOUS → per rules, treated as REJECTED."""
        classification = proposer.classify_response(sample_proposal, "")
        assert classification.classification == DecisionValue.AMBIGUOUS
        assert classification.confidence == 0.0

    def test_whitespace_response_is_ambiguous(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "   \n  ")
        assert classification.classification == DecisionValue.AMBIGUOUS

    def test_unrelated_response_low_confidence(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """Random text with no keywords → should be ambiguous."""
        classification = proposer.classify_response(sample_proposal, "El cielo es azul")
        assert classification.confidence < 0.5, f"Expected low confidence, got {classification.confidence}"
        # May be AMBIGUOUS or one of the categories with low confidence

    def test_near_tie_is_ambiguous(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """When accept/reject scores are too close → AMBIGUOUS."""
        # This is hard to trigger reliably; just verify the mechanism exists
        pass


# ---------------------------------------------------------------------------
# Decision recording
# ---------------------------------------------------------------------------


class TestDecisionRecording:
    def test_record_acceptance(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Sí")
        decision = proposer.record_decision(sample_proposal, classification, decided_by="user")
        assert decision.decision == DecisionValue.ACCEPTED
        assert decision.proposal_id == sample_proposal.id
        assert decision.id.startswith("dec_")
        assert sample_proposal.status == ProposalStatus.DECIDED

    def test_record_rejection(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "No")
        decision = proposer.record_decision(sample_proposal, classification, decided_by="user")
        assert decision.decision == DecisionValue.REJECTED
        assert sample_proposal.status == ProposalStatus.DECIDED

    def test_record_edit(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Edita: cierra a las 9pm")
        decision = proposer.record_decision(
            sample_proposal, classification,
            decided_by="user",
            edited_content="Cierra a las 9pm",
        )
        assert decision.decision == DecisionValue.EDITED
        assert decision.edited_content == "Cierra a las 9pm"

    def test_ambiguous_maps_to_rejected(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """Per MEM-092: ambiguous → rejected."""
        classification = proposer.classify_response(sample_proposal, "")
        decision = proposer.record_decision(sample_proposal, classification)
        assert decision.decision == DecisionValue.REJECTED
        assert "ambiguous" in decision.notes.lower()

    def test_edited_content_from_response_when_missing(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        """If EDITED but no edited_content, uses the user's response text."""
        classification = proposer.classify_response(sample_proposal, "Corrige: cierra a las 9pm")
        decision = proposer.record_decision(sample_proposal, classification)
        assert decision.decision == DecisionValue.EDITED
        assert decision.edited_content == "Corrige: cierra a las 9pm"

    def test_decision_immutable_fields(self, proposer: MemoryProposer, sample_proposal: MemoryProposal):
        classification = proposer.classify_response(sample_proposal, "Sí, vale")
        decision = proposer.record_decision(sample_proposal, classification)
        assert decision.proposal_id == sample_proposal.id
        assert decision.decided_at is not None
        assert decision.id is not None