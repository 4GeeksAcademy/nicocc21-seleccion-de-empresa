"""Tests for MemoryConsolidator — grouping entries by (location_id, category)."""

from __future__ import annotations

import pytest
from pathlib import Path

from agents.support_agent.memory.memory_consolidator import MemoryConsolidator
from agents.support_agent.memory.memory_store import MemoryStore
from agents.support_agent.memory.schemas import (
    ConsolidatedMemory,
    MemoryCategory,
    MemoryEntry,
    MemorySource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(store_dir=str(tmp_path / "memory"))


@pytest.fixture
def consolidator(store: MemoryStore) -> MemoryConsolidator:
    return MemoryConsolidator(store, min_entries_for_consolidation=2)


def make_entry(
    location_id: str,
    category: MemoryCategory,
    content: str,
    language: str = "es",
) -> MemoryEntry:
    return MemoryEntry(
        location_id=location_id,
        category=category,
        content=content,
        language=language,
        source=MemorySource.USER_CORRECTION,
    )


# ---------------------------------------------------------------------------
# Grouping logic
# ---------------------------------------------------------------------------


class TestGrouping:
    def test_groups_by_location_and_category(self, consolidator: MemoryConsolidator, store: MemoryStore):
        """Entries with same (location, category) should be grouped."""
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am")
        e3 = make_entry("L01", MemoryCategory.SUPPLIERS, "Carne los lunes")
        store.save_entry(e1)
        store.save_entry(e2)
        store.save_entry(e3)

        groups = consolidator._group_entries(store.get_entries(active_only=True))
        assert len(groups) == 2
        assert ("L01", MemoryCategory.SCHEDULES) in groups
        assert ("L01", MemoryCategory.SUPPLIERS) in groups

    def test_different_locations_separate(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L02", MemoryCategory.SCHEDULES, "Cierra a las 9pm")
        store.save_entry(e1)
        store.save_entry(e2)

        groups = consolidator._group_entries(store.get_entries(active_only=True))
        assert len(groups) == 2

    def test_single_entry_not_grouped(self, consolidator: MemoryConsolidator, store: MemoryStore):
        """Groups with only 1 entry should not be consolidated (min=2)."""
        e = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        store.save_entry(e)

        consolidations = consolidator.consolidate_all()
        assert len(consolidations) == 0


# ---------------------------------------------------------------------------
# Consolidation execution
# ---------------------------------------------------------------------------


class TestConsolidation:
    def test_consolidate_all(self, consolidator: MemoryConsolidator, store: MemoryStore):
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm"))
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am"))
        store.save_entry(make_entry("L01", MemoryCategory.SUPPLIERS, "Carne los lunes"))

        results = consolidator.consolidate_all()
        # Only SCHEDULES has 2 entries
        assert len(results) == 1
        assert results[0].category == MemoryCategory.SCHEDULES
        assert results[0].entries_count == 2

    def test_consolidate_location(self, consolidator: MemoryConsolidator, store: MemoryStore):
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm"))
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am"))
        store.save_entry(make_entry("L02", MemoryCategory.SCHEDULES, "Cierra a las 9pm"))

        results = consolidator.consolidate_location("L01")
        assert len(results) == 1

        results_l2 = consolidator.consolidate_location("L02")
        assert len(results_l2) == 0  # Only 1 entry for L02

    def test_consolidation_updates_existing(self, consolidator: MemoryConsolidator, store: MemoryStore):
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm"))
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am"))
        first = consolidator.consolidate_all()
        v1 = first[0].version

        # Add another entry and re-consolidate
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Nuevo horario"))
        second = consolidator.consolidate_all()
        assert len(second) == 1
        assert second[0].version > v1
        assert second[0].entries_count == 3

    def test_consolidation_with_different_min(self, store: MemoryStore):
        """Test with min_entries=1 to verify single-entry consolidation."""
        c = MemoryConsolidator(store, min_entries_for_consolidation=1)
        store.save_entry(make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm"))
        results = c.consolidate_all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


class TestSummaryGeneration:
    def test_single_entry_summary(self, consolidator: MemoryConsolidator, store: MemoryStore):
        entry = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        store.save_entry(entry)
        groups = consolidator._group_entries([entry])
        con = consolidator._consolidate_group("L01", MemoryCategory.SCHEDULES, [entry])
        assert con.summary == "Cierra a las 10pm"

    def test_bullet_summary_for_schedules(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am")
        con = consolidator._consolidate_group("L01", MemoryCategory.SCHEDULES, [e1, e2])
        assert con.summary.startswith("•")
        assert "Cierra" in con.summary
        assert "Abre" in con.summary

    def test_bullet_summary_for_suppliers(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.SUPPLIERS, "Carne los lunes")
        e2 = make_entry("L01", MemoryCategory.SUPPLIERS, "Pan los miércoles")
        con = consolidator._consolidate_group("L01", MemoryCategory.SUPPLIERS, [e1, e2])
        assert con.summary.startswith("•")

    def test_pipe_summary_for_incidents(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.KNOWN_INCIDENTS, "Corte de luz")
        e2 = make_entry("L01", MemoryCategory.KNOWN_INCIDENTS, "Error en POS")
        con = consolidator._consolidate_group("L01", MemoryCategory.KNOWN_INCIDENTS, [e1, e2])
        assert "|" in con.summary

    def test_deduplication(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")  # Duplicate
        e3 = make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am")
        con = consolidator._consolidate_group("L01", MemoryCategory.SCHEDULES, [e1, e2, e3])
        # "Cierra a las 10pm" should appear only once
        assert con.summary.count("Cierra a las 10pm") == 1

    def test_summary_max_length(self, consolidator: MemoryConsolidator, store: MemoryStore):
        """Long summaries should be truncated."""
        long_content = "X" * 300
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, long_content)
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Y" * 300)
        con = consolidator._consolidate_group("L01", MemoryCategory.SCHEDULES, [e1, e2])
        assert len(con.summary) <= consolidator._max_summary_length + 20  # Allow small overhead

    def test_empty_summary(self, consolidator: MemoryConsolidator):
        """No entries → empty summary."""
        # Can't call _consolidate_group with empty list, check _build_summary
        summary = consolidator._build_summary(MemoryCategory.OTHER, [])
        assert summary == ""


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestLanguageDetection:
    def test_majority_language_spanish(self):
        entries = [
            make_entry("L01", MemoryCategory.OTHER, "Hola", language="es"),
            make_entry("L01", MemoryCategory.OTHER, "Adiós", language="es"),
            make_entry("L01", MemoryCategory.OTHER, "Hello", language="en"),
        ]
        lang = MemoryConsolidator._majority_language(entries)
        assert lang == "es"

    def test_majority_language_english(self):
        entries = [
            make_entry("L01", MemoryCategory.OTHER, "Hello", language="en"),
            make_entry("L01", MemoryCategory.OTHER, "Goodbye", language="en"),
            make_entry("L01", MemoryCategory.OTHER, "Hola", language="es"),
        ]
        lang = MemoryConsolidator._majority_language(entries)
        assert lang == "en"

    def test_majority_language_empty(self):
        lang = MemoryConsolidator._majority_language([])
        assert lang == "es"  # Default


# ---------------------------------------------------------------------------
# Deconsolidation
# ---------------------------------------------------------------------------


class TestDeconsolidation:
    def test_deconsolidate_removes_entry(self, consolidator: MemoryConsolidator, store: MemoryStore):
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am")
        store.save_entry(e1)
        store.save_entry(e2)
        consolidator.consolidate_all()

        # Deconsolidate e1
        result = consolidator.deconsolidate_entry(e1.id)
        assert result is not None
        assert e1.id not in result.entry_ids
        assert result.entries_count == 1

    def test_deconsolidate_nonexistent(self, consolidator: MemoryConsolidator):
        result = consolidator.deconsolidate_entry("nonexistent")
        assert result is None

    def test_deconsolidate_empty_group(self, consolidator: MemoryConsolidator, store: MemoryStore):
        """Removing all entries should produce empty summary."""
        e1 = make_entry("L01", MemoryCategory.SCHEDULES, "Cierra a las 10pm")
        e2 = make_entry("L01", MemoryCategory.SCHEDULES, "Abre a las 8am")
        store.save_entry(e1)
        store.save_entry(e2)
        consolidator.consolidate_all()

        consolidator.deconsolidate_entry(e1.id)
        result = consolidator.deconsolidate_entry(e2.id)
        assert result is not None
        assert result.summary == ""
        assert result.entries_count == 0