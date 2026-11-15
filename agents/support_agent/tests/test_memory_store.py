"""Tests for MemoryStore — persistent JSON storage with thread-safe CRUD."""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from agents.support_agent.memory.memory_store import MemoryStore
from agents.support_agent.memory.schemas import (
    ConsolidatedMemory,
    DecisionValue,
    MemoryCategory,
    MemoryDecision,
    MemoryEntry,
    MemoryProposal,
    MemorySource,
    ProposalStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    """Create a MemoryStore with a temporary directory."""
    return MemoryStore(store_dir=str(tmp_path / "memory"))


@pytest.fixture
def sample_entry() -> MemoryEntry:
    return MemoryEntry(
        location_id="L03",
        category=MemoryCategory.SCHEDULES,
        content="El local cierra a las 10pm los viernes",
        language="es",
        source=MemorySource.USER_CORRECTION,
    )


@pytest.fixture
def sample_proposal() -> MemoryProposal:
    return MemoryProposal(
        location_id="L03",
        category=MemoryCategory.SCHEDULES,
        content="El local cierra a las 10pm los viernes",
        source=MemorySource.USER_CORRECTION,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )


# ---------------------------------------------------------------------------
# Store initialization
# ---------------------------------------------------------------------------


class TestStoreInit:
    def test_creates_directory(self, tmp_path: Path):
        store_path = tmp_path / "test_mem"
        assert not store_path.exists()
        MemoryStore(store_dir=str(store_path))
        assert store_path.is_dir()

    def test_creates_store_file(self, tmp_path: Path):
        store = MemoryStore(store_dir=str(tmp_path / "mem"))
        store_file = store._store_file
        assert store_file.exists()

    def test_initializes_empty(self, store: MemoryStore):
        info = store.store_info()
        assert info["total_entries"] == 0
        assert info["total_proposals"] == 0
        assert info["total_decisions"] == 0
        assert info["total_consolidations"] == 0

    def test_loads_existing_store(self, tmp_path: Path):
        """Verify store can load previously saved data."""
        store1 = MemoryStore(store_dir=str(tmp_path / "mem2"))
        entry = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Test")
        store1.save_entry(entry)

        store2 = MemoryStore(store_dir=str(tmp_path / "mem2"))
        assert store2.get_entry(entry.id) is not None
        assert store2.count_entries() == 1


# ---------------------------------------------------------------------------
# Entries CRUD
# ---------------------------------------------------------------------------


class TestEntriesCRUD:
    def test_save_and_get_entry(self, store: MemoryStore, sample_entry: MemoryEntry):
        saved = store.save_entry(sample_entry)
        assert saved.id == sample_entry.id
        assert saved.version == 1

        retrieved = store.get_entry(sample_entry.id)
        assert retrieved is not None
        assert retrieved.content == sample_entry.content
        assert retrieved.location_id == "L03"

    def test_save_updates_version(self, store: MemoryStore, sample_entry: MemoryEntry):
        store.save_entry(sample_entry)
        sample_entry.content = "Updated content"
        updated = store.save_entry(sample_entry)
        assert updated.version == 2

    def test_get_entries_filters_by_location(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="A")
        e2 = MemoryEntry(location_id="L02", category=MemoryCategory.OTHER, content="B")
        e3 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="C")
        store.save_entry(e1)
        store.save_entry(e2)
        store.save_entry(e3)

        loc1 = store.get_entries(location_id="L01")
        assert len(loc1) == 2

        loc2 = store.get_entries(location_id="L02")
        assert len(loc2) == 1

    def test_get_entries_filters_by_category(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.SCHEDULES, content="A")
        e2 = MemoryEntry(location_id="L01", category=MemoryCategory.SUPPLIERS, content="B")
        store.save_entry(e1)
        store.save_entry(e2)

        schedules = store.get_entries(category="horarios")
        assert len(schedules) == 1

    def test_get_entries_active_only(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Active")
        e2 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Inactive")
        store.save_entry(e1)
        store.save_entry(e2)
        store.soft_delete_entry(e2.id)

        active = store.get_entries(active_only=True)
        assert len(active) == 1
        assert active[0].id == e1.id

        all_entries = store.get_entries(active_only=False)
        assert len(all_entries) == 2

    def test_entries_ordered_by_date_desc(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Old")
        e2 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="New")
        store.save_entry(e1)
        store.save_entry(e2)

        entries = store.get_entries()
        assert entries[0].id == e2.id  # Newest first

    def test_soft_delete(self, store: MemoryStore, sample_entry: MemoryEntry):
        store.save_entry(sample_entry)
        assert store.soft_delete_entry(sample_entry.id) is True
        entry = store.get_entry(sample_entry.id)
        assert entry is not None
        assert entry.is_active is False

    def test_soft_delete_nonexistent(self, store: MemoryStore):
        assert store.soft_delete_entry("nonexistent") is False

    def test_hard_delete(self, store: MemoryStore, sample_entry: MemoryEntry):
        store.save_entry(sample_entry)
        assert store.hard_delete_entry(sample_entry.id) is True
        assert store.get_entry(sample_entry.id) is None

    def test_hard_delete_nonexistent(self, store: MemoryStore):
        assert store.hard_delete_entry("nonexistent") is False


# ---------------------------------------------------------------------------
# Proposals CRUD
# ---------------------------------------------------------------------------


class TestProposalsCRUD:
    def test_save_and_get_proposal(self, store: MemoryStore, sample_proposal: MemoryProposal):
        saved = store.save_proposal(sample_proposal)
        assert saved.id == sample_proposal.id

        retrieved = store.get_proposal(sample_proposal.id)
        assert retrieved is not None
        assert retrieved.content == sample_proposal.content

    def test_get_pending_proposals(self, store: MemoryStore, sample_proposal: MemoryProposal):
        store.save_proposal(sample_proposal)
        pending = store.get_pending_proposals()
        assert len(pending) == 1

    def test_expired_proposal_not_pending(self, store: MemoryStore):
        expired = MemoryProposal(
            location_id="L03",
            category=MemoryCategory.OTHER,
            content="Expired",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        store.save_proposal(expired)
        pending = store.get_pending_proposals()
        assert len(pending) == 0

    def test_get_pending_proposals_filters_location(self, store: MemoryStore):
        p1 = MemoryProposal(location_id="L01", category=MemoryCategory.OTHER, content="A")
        p2 = MemoryProposal(location_id="L02", category=MemoryCategory.OTHER, content="B")
        store.save_proposal(p1)
        store.save_proposal(p2)

        loc1 = store.get_pending_proposals(location_id="L01")
        assert len(loc1) == 1
        assert loc1[0].id == p1.id

    def test_update_proposal_status(self, store: MemoryStore, sample_proposal: MemoryProposal):
        store.save_proposal(sample_proposal)
        assert store.update_proposal_status(sample_proposal.id, ProposalStatus.DECIDED) is True
        prop = store.get_proposal(sample_proposal.id)
        assert prop.status == ProposalStatus.DECIDED

    def test_update_proposal_status_nonexistent(self, store: MemoryStore):
        assert store.update_proposal_status("nonexistent", ProposalStatus.DECIDED) is False


# ---------------------------------------------------------------------------
# Decisions CRUD
# ---------------------------------------------------------------------------


class TestDecisionsCRUD:
    def test_save_and_get_decision(self, store: MemoryStore):
        decision = MemoryDecision(
            proposal_id="prop_test",
            decision=DecisionValue.ACCEPTED,
            decided_by="user",
        )
        saved = store.save_decision(decision)
        assert saved.id == decision.id

        retrieved = store.get_decision(decision.id)
        assert retrieved is not None
        assert retrieved.decision == DecisionValue.ACCEPTED

    def test_decisions_are_immutable(self, store: MemoryStore):
        decision = MemoryDecision(
            proposal_id="prop_test",
            decision=DecisionValue.ACCEPTED,
        )
        store.save_decision(decision)
        with pytest.raises(ValueError, match="already exists"):
            store.save_decision(decision)

    def test_get_decisions_for_proposal(self, store: MemoryStore):
        d1 = MemoryDecision(proposal_id="prop_1", decision=DecisionValue.ACCEPTED)
        d2 = MemoryDecision(proposal_id="prop_1", decision=DecisionValue.REJECTED)
        d3 = MemoryDecision(proposal_id="prop_2", decision=DecisionValue.ACCEPTED)
        store.save_decision(d1)
        store.save_decision(d2)
        store.save_decision(d3)

        decisions = store.get_decisions_for_proposal("prop_1")
        assert len(decisions) == 2

    def test_get_decisions_filters(self, store: MemoryStore):
        # Create a proposal + decision to test location filter
        prop = MemoryProposal(location_id="L01", category=MemoryCategory.OTHER, content="Test")
        store.save_proposal(prop)

        d1 = MemoryDecision(proposal_id=prop.id, decision=DecisionValue.ACCEPTED)
        d2 = MemoryDecision(proposal_id="other_prop", decision=DecisionValue.REJECTED)
        store.save_decision(d1)
        store.save_decision(d2)

        accepted = store.get_decisions(decision_type=DecisionValue.ACCEPTED)
        assert len(accepted) == 1
        assert accepted[0].id == d1.id


# ---------------------------------------------------------------------------
# Consolidations CRUD
# ---------------------------------------------------------------------------


class TestConsolidationsCRUD:
    def test_save_and_get_consolidation(self, store: MemoryStore):
        con = ConsolidatedMemory(
            location_id="L03",
            category=MemoryCategory.SCHEDULES,
            summary="Test summary",
        )
        saved = store.save_consolidation(con)
        assert saved.id == con.id

        retrieved = store.get_consolidation(con.id)
        assert retrieved is not None
        assert retrieved.summary == "Test summary"

    def test_get_consolidations_for_location(self, store: MemoryStore):
        c1 = ConsolidatedMemory(location_id="L01", category=MemoryCategory.SCHEDULES)
        c2 = ConsolidatedMemory(location_id="L01", category=MemoryCategory.SUPPLIERS)
        c3 = ConsolidatedMemory(location_id="L02", category=MemoryCategory.SCHEDULES)
        store.save_consolidation(c1)
        store.save_consolidation(c2)
        store.save_consolidation(c3)

        loc1 = store.get_consolidations_for_location("L01")
        assert len(loc1) == 2

        loc2 = store.get_consolidations_for_location("L02")
        assert len(loc2) == 1

    def test_get_consolidation_by_group(self, store: MemoryStore):
        c = ConsolidatedMemory(location_id="L03", category=MemoryCategory.SCHEDULES)
        store.save_consolidation(c)

        found = store.get_consolidation_by_group("L03", "horarios")
        assert found is not None
        assert found.id == c.id

        not_found = store.get_consolidation_by_group("L03", "proveedores")
        assert not_found is None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_entries_by_text(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.SCHEDULES, content="Cierra a las 10pm")
        e2 = MemoryEntry(location_id="L01", category=MemoryCategory.SUPPLIERS, content="Proveedor de carne")
        e3 = MemoryEntry(location_id="L02", category=MemoryCategory.SCHEDULES, content="Abre a las 8am")
        store.save_entry(e1)
        store.save_entry(e2)
        store.save_entry(e3)

        results = store.search_entries("carne")
        assert len(results) == 1
        assert results[0].id == e2.id

    def test_search_case_insensitive(self, store: MemoryStore):
        e = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Cierra a las 10PM")
        store.save_entry(e)

        results = store.search_entries("10pm")
        assert len(results) == 1

    def test_search_filters_by_location(self, store: MemoryStore):
        e1 = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Cierra a las 10pm")
        e2 = MemoryEntry(location_id="L02", category=MemoryCategory.OTHER, content="Cierra a las 10pm")
        store.save_entry(e1)
        store.save_entry(e2)

        results = store.search_entries("cierra", location_id="L01")
        assert len(results) == 1
        assert results[0].id == e1.id

    def test_search_ignores_inactive(self, store: MemoryStore):
        e = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Test")
        store.save_entry(e)
        store.soft_delete_entry(e.id)

        results = store.search_entries("Test")
        assert len(results) == 0

    def test_search_empty_query(self, store: MemoryStore):
        assert store.search_entries("") == []
        assert store.search_entries("   ") == []

    def test_search_bilingual(self, store: MemoryStore):
        e_es = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Cierra a las 10pm", language="es")
        e_en = MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="Closes at 10pm", language="en")
        store.save_entry(e_es)
        store.save_entry(e_en)

        assert len(store.search_entries("cierra")) == 1
        assert len(store.search_entries("closes")) == 1


# ---------------------------------------------------------------------------
# Store info and helpers
# ---------------------------------------------------------------------------


class TestStoreInfo:
    def test_store_info_counts(self, store: MemoryStore):
        store.save_entry(MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="A"))
        store.save_entry(MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="B"))
        store.save_proposal(MemoryProposal(location_id="L01", category=MemoryCategory.OTHER, content="C"))
        store.save_decision(MemoryDecision(proposal_id="p1", decision=DecisionValue.ACCEPTED))
        store.save_consolidation(ConsolidatedMemory(location_id="L01", category=MemoryCategory.OTHER))

        info = store.store_info()
        assert info["active_entries"] == 2
        assert info["total_proposals"] == 1
        assert info["total_decisions"] == 1
        assert info["total_consolidations"] == 1

    def test_get_all_location_ids(self, store: MemoryStore):
        store.save_entry(MemoryEntry(location_id="L03", category=MemoryCategory.OTHER, content="A"))
        store.save_entry(MemoryEntry(location_id="L01", category=MemoryCategory.OTHER, content="B"))

        locs = store.get_all_location_ids()
        assert locs == ["L01", "L03"]

    def test_get_all_location_ids_empty(self, store: MemoryStore):
        assert store.get_all_location_ids() == []


# ---------------------------------------------------------------------------
# Thread safety and persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_atomic_write(self, store: MemoryStore, sample_entry: MemoryEntry):
        """Verify no .tmp files remain after save."""
        store.save_entry(sample_entry)
        tmp_files = list(store._store_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_json_structure(self, store: MemoryStore, sample_entry: MemoryEntry):
        store.save_entry(sample_entry)
        with open(store._store_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "entries" in data
        assert "proposals" in data
        assert "decisions" in data
        assert "consolidations" in data
        assert "store_version" in data
        assert "last_consolidated" in data