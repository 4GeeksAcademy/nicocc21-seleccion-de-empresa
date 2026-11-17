"""Tests for MemoryManager — orchestrator of the full memory flow."""

from __future__ import annotations

import pytest
from pathlib import Path

from agents.support_agent.memory.memory_manager import MemoryManager
from agents.support_agent.memory.memory_store import MemoryStore
from agents.support_agent.memory.memory_evaluator import MemoryEvaluator
from agents.support_agent.memory.memory_proposer import MemoryProposer
from agents.support_agent.memory.memory_consolidator import MemoryConsolidator
from agents.support_agent.memory.schemas import (
    DecisionValue,
    MemoryCategory,
    MemoryEntry,
    MemoryProposal,
    MemorySource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(store_dir=str(tmp_path / "memory"))


@pytest.fixture
def evaluator() -> MemoryEvaluator:
    return MemoryEvaluator(confidence_threshold=0.4)


@pytest.fixture
def proposer() -> MemoryProposer:
    return MemoryProposer(
        classification_confidence_threshold=0.5,
        proposal_ttl_minutes=30,
    )


@pytest.fixture
def manager(store: MemoryStore) -> MemoryManager:
    return MemoryManager(
        store=store,
        evaluator=MemoryEvaluator(confidence_threshold=0.4),
        proposer=MemoryProposer(classification_confidence_threshold=0.5),
        consolidator=MemoryConsolidator(store, min_entries_for_consolidation=2),
    )


# ---------------------------------------------------------------------------
# evaluate_and_propose — full flow
# ---------------------------------------------------------------------------


class TestEvaluateAndPropose:
    def test_memorable_text_creates_proposal(self, manager: MemoryManager):
        """Text that matches patterns → proposal + prompt returned."""
        proposal, prompt = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm los viernes",
            location_id="L03",
        )
        assert proposal is not None
        assert prompt is not None
        assert "recuerde esto" in prompt
        assert proposal.location_id == "L03"

    def test_non_memorable_text_returns_none(self, manager: MemoryManager):
        """Text with no patterns → None, None."""
        proposal, prompt = manager.evaluate_and_propose(
            interaction_text="Hola, ¿cómo estás?",
            location_id="L03",
        )
        assert proposal is None
        assert prompt is None

    def test_sensitive_text_returns_none(self, manager: MemoryManager):
        """Personal data → should not propose."""
        proposal, prompt = manager.evaluate_and_propose(
            interaction_text="Mi DNI es 12345678Z",
            location_id="L03",
        )
        assert proposal is None
        assert prompt is None

    def test_proposal_persisted_to_store(self, manager: MemoryManager):
        """Proposal should be saved in the store."""
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El proveedor de carne pasa los lunes",
            location_id="L03",
        )
        assert proposal is not None
        stored = manager._store.get_proposal(proposal.id)
        assert stored is not None
        assert stored.status.value == "pending"

    def test_english_language_prompt(self, manager: MemoryManager):
        """English language → prompt in English."""
        _, prompt = manager.evaluate_and_propose(
            interaction_text="The store closes at 10pm",
            location_id="L03",
            language="en",
        )
        assert prompt is not None
        assert "Would you like me to remember" in prompt

    def test_proposal_tracked_as_pending(self, manager: MemoryManager):
        """Pending proposals tracked in MemoryManager._pending_proposals."""
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm",
            location_id="L03",
        )
        assert proposal is not None
        assert proposal.id in manager._pending_proposals


# ---------------------------------------------------------------------------
# process_decision — user response processing
# ---------------------------------------------------------------------------


class TestProcessDecision:
    def test_process_accept(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm los viernes",
            location_id="L03",
        )
        assert proposal is not None

        decision, entry = manager.process_decision(
            proposal_id=proposal.id,
            user_response="Sí, guárdalo",
            decided_by="user",
        )
        assert decision.decision == DecisionValue.ACCEPTED
        assert entry is not None
        assert entry.location_id == "L03"
        assert entry.category == MemoryCategory.SCHEDULES

    def test_process_reject(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm los viernes",
            location_id="L03",
        )
        assert proposal is not None

        decision, entry = manager.process_decision(
            proposal_id=proposal.id,
            user_response="No, no hace falta",
            decided_by="user",
        )
        assert decision.decision == DecisionValue.REJECTED
        assert entry is None  # No entry created

    def test_process_edit(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm",
            location_id="L03",
        )
        assert proposal is not None

        decision, entry = manager.process_decision(
            proposal_id=proposal.id,
            user_response="Corrige: cierra a las 9pm",
            decided_by="user",
        )
        assert decision.decision == DecisionValue.EDITED
        assert entry is not None
        assert entry.content == "Corrige: cierra a las 9pm"

    def test_process_ambiguous_as_rejected(self, manager: MemoryManager):
        """Ambiguous classification → decision is REJECTED."""
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm",
            location_id="L03",
        )
        assert proposal is not None

        decision, entry = manager.process_decision(
            proposal_id=proposal.id,
            user_response="",
            decided_by="user",
        )
        assert decision.decision == DecisionValue.REJECTED
        assert entry is None

    def test_process_nonexistent_proposal(self, manager: MemoryManager):
        with pytest.raises(ValueError, match="not found"):
            manager.process_decision(
                proposal_id="nonexistent",
                user_response="Sí",
            )

    def test_process_already_decided_proposal(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm",
            location_id="L03",
        )
        assert proposal is not None

        manager.process_decision(proposal.id, "Sí")
        with pytest.raises(ValueError, match="already decided"):
            manager.process_decision(proposal.id, "No")

    def test_decision_persisted(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm",
            location_id="L03",
        )
        assert proposal is not None

        decision, _ = manager.process_decision(proposal.id, "Sí")
        stored = manager._store.get_decision(decision.id)
        assert stored is not None
        assert stored.decision == DecisionValue.ACCEPTED

    def test_entry_persisted_after_accept(self, manager: MemoryManager):
        proposal, _ = manager.evaluate_and_propose(
            interaction_text="El local cierra a las 10pm los viernes",
            location_id="L03",
        )
        assert proposal is not None

        _, entry = manager.process_decision(proposal.id, "Sí")
        assert entry is not None
        stored = manager._store.get_entry(entry.id)
        assert stored is not None
        assert stored.content == "El local cierra a las 10pm los viernes"

    def test_consolidation_triggered_on_accept(self, manager: MemoryManager):
        """Accepting multiple entries for same group should trigger consolidation."""
        # First entry
        p1, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p1.id, "Sí")

        # Second entry for same location+category
        p2, _ = manager.evaluate_and_propose(
            "El local abre a las 8am", "L03",
        )
        manager.process_decision(p2.id, "Sí")

        # Check consolidation exists
        cons = manager._store.get_consolidation_by_group("L03", "horarios")
        assert cons is not None
        assert cons.entries_count >= 2


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------


class TestContextInjection:
    def test_get_context_empty(self, manager: MemoryManager):
        """No memories → empty string."""
        ctx = manager.get_context("L03")
        assert ctx == ""

    def test_get_context_with_memories(self, manager: MemoryManager):
        p, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p.id, "Sí")

        ctx = manager.get_context("L03")
        assert ctx != ""
        assert "L03" in ctx
        assert "Memoria" in ctx or "memory" in ctx.lower()

    def test_get_context_with_categories_filter(self, manager: MemoryManager):
        p1, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p1.id, "Sí")

        p2, _ = manager.evaluate_and_propose(
            "El proveedor de carne pasa los lunes", "L03",
        )
        manager.process_decision(p2.id, "Sí")

        # Filter only SCHEDULES
        ctx = manager.get_context("L03", categories=[MemoryCategory.SCHEDULES])
        assert "proveedor" not in ctx.lower()

    def test_get_context_different_locations(self, manager: MemoryManager):
        """Context for one location should not include other locations."""
        p, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p.id, "Sí")

        ctx = manager.get_context("L01")
        assert ctx == ""

    def test_get_context_without_consolidated(self, manager: MemoryManager):
        """Without consolidation, raw entries should still appear."""
        p, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p.id, "Sí")

        ctx_raw = manager.get_context("L03", include_consolidated=False)
        assert ctx_raw != ""
        assert "cierra" in ctx_raw.lower()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    def test_get_pending_proposals(self, manager: MemoryManager):
        manager.evaluate_and_propose("El local cierra a las 10pm", "L03")
        pending = manager.get_pending_proposals()
        assert len(pending) == 1
        assert pending[0].location_id == "L03"

    def test_get_store_info(self, manager: MemoryManager):
        info = manager.get_store_info()
        assert "active_entries" in info
        assert "pending_proposals" in info
        assert "total_decisions" in info

    def test_search_memories(self, manager: MemoryManager):
        p, _ = manager.evaluate_and_propose(
            "El local cierra a las 10pm", "L03",
        )
        manager.process_decision(p.id, "Sí")

        results = manager.search_memories("cierra")
        assert len(results) == 1

    def test_search_memories_no_results(self, manager: MemoryManager):
        results = manager.search_memories("nonexistent")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Consolidation helpers
# ---------------------------------------------------------------------------


class TestConsolidationHelpers:
    def test_consolidate_all(self, manager: MemoryManager):
        p1, _ = manager.evaluate_and_propose("Cierra a las 10pm", "L03")
        manager.process_decision(p1.id, "Sí")
        p2, _ = manager.evaluate_and_propose("Abre a las 8am", "L03")
        manager.process_decision(p2.id, "Sí")

        results = manager.consolidate_all()
        assert len(results) >= 1

    def test_consolidate_location(self, manager: MemoryManager):
        p1, _ = manager.evaluate_and_propose("Cierra a las 10pm", "L03")
        manager.process_decision(p1.id, "Sí")
        p2, _ = manager.evaluate_and_propose("Abre a las 8am", "L03")
        manager.process_decision(p2.id, "Sí")

        results = manager.consolidate_location("L03")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# MemoryManager initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_initialization(self):
        """Can create MemoryManager with no arguments (auto-creates store)."""
        mm = MemoryManager()
        assert mm._store is not None
        assert mm._evaluator is not None
        assert mm._proposer is not None
        assert mm._consolidator is not None
        assert mm._pending_proposals == {}

    def test_custom_components(self, store: MemoryStore):
        """Can inject custom components."""
        mm = MemoryManager(store=store)
        assert mm._store is store