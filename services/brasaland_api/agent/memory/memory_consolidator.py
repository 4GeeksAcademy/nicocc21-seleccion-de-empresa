"""
Consolidation engine: groups memory entries by location + category.

Generates summaries and merges similar entries to prevent
unbounded memory growth.

Per the company briefing:
    "Con 14 locations activas, la memoria episódica puede crecer rápido
     si no se agrupa por location. Considera que la consolidación resuma
     por location + categoría en vez de guardar cada corrección como una
     entrada suelta."

Design decision — justify here:
    We consolidate by (location_id, category) because:
    1. Location is the primary axis — each location has independent schedules,
       suppliers, and incidents.
    2. Category is the secondary axis — "proveedores" facts for Medellín
       should be separate from "horarios" facts for Medellín.
    3. This 2D grouping keeps summaries concise and retrievable.
    4. Alternative: global summaries lose location specificity; per-entry
       storage without consolidation grows unboundedly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .schemas import (
    ConsolidatedMemory,
    MemoryCategory,
    MemoryEntry,
)
from .memory_store import MemoryStore

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Consolidator
# ──────────────────────────────────────────────


class MemoryConsolidator:
    """
    Consolidates memory entries by (location_id, category).

    Instead of storing every correction as a separate entry,
    related facts are grouped into a single consolidated summary.
    """

    def __init__(
        self,
        store: MemoryStore,
        min_entries_for_consolidation: int = 2,
        max_summary_length: int = 500,
    ):
        self._store = store
        self._min_entries = min_entries_for_consolidation
        self._max_summary_length = max_summary_length

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def consolidate_all(self) -> list[ConsolidatedMemory]:
        """
        Consolidate ALL active entries grouped by (location_id, category).

        Returns the list of created/updated consolidations.
        """
        all_entries = self._store.get_entries(active_only=True)
        groups = self._group_entries(all_entries)

        consolidations: list[ConsolidatedMemory] = []
        for (location_id, category), entries in groups.items():
            if len(entries) < self._min_entries:
                logger.debug(
                    "Skipping consolidation for %s/%s: only %d entries (min %d)",
                    location_id,
                    category.value,
                    len(entries),
                    self._min_entries,
                )
                continue

            consolidated = self._consolidate_group(location_id, category, entries)
            saved = self._store.save_consolidation(consolidated)
            consolidations.append(saved)

        # Update last_consolidated timestamp
        if consolidations:
            self._store._data.last_consolidated = datetime.now(timezone.utc)
            self._store._save()

        logger.info(
            "Consolidation complete: %d groups consolidated from %d entries",
            len(consolidations),
            len(all_entries),
        )
        return consolidations

    def consolidate_location(
        self, location_id: str
    ) -> list[ConsolidatedMemory]:
        """
        Consolidate entries for a single location.
        Useful after adding new memory for a specific location.
        """
        entries = self._store.get_entries(location_id=location_id, active_only=True)
        groups = self._group_entries(entries)

        consolidations: list[ConsolidatedMemory] = []
        for (loc, category), group_entries in groups.items():
            if len(group_entries) < self._min_entries:
                continue
            consolidated = self._consolidate_group(loc, category, group_entries)
            saved = self._store.save_consolidation(consolidated)
            consolidations.append(saved)

        if consolidations:
            self._store._data.last_consolidated = datetime.now(timezone.utc)
            self._store._save()

        return consolidations

    # ──────────────────────────────────────────
    # Grouping
    # ──────────────────────────────────────────

    def _group_entries(
        self, entries: list[MemoryEntry]
    ) -> dict[tuple[str, MemoryCategory], list[MemoryEntry]]:
        """
        Group entries by (location_id, category).

        This is the core grouping strategy: 2D by location + category.
        """
        groups: dict[tuple[str, MemoryCategory], list[MemoryEntry]] = {}
        for entry in entries:
            key = (entry.location_id, entry.category)
            if key not in groups:
                groups[key] = []
            groups[key].append(entry)
        return groups

    # ──────────────────────────────────────────
    # Summary generation
    # ──────────────────────────────────────────

    def _consolidate_group(
        self,
        location_id: str,
        category: MemoryCategory,
        entries: list[MemoryEntry],
    ) -> ConsolidatedMemory:
        """
        Create or update a ConsolidatedMemory for a group of entries.

        The summary is built by concatenating unique content strings,
        deduplicated and truncated to max_summary_length.
        """
        # Sort by created_at descending (newest first)
        entries.sort(key=lambda e: e.created_at, reverse=True)

        # Deduplicate content (case-insensitive)
        seen = set()
        unique_contents: list[str] = []
        for entry in entries:
            key = entry.content.strip().lower()
            if key not in seen:
                seen.add(key)
                unique_contents.append(entry.content.strip())

        # Build summary
        summary = self._build_summary(category, unique_contents)

        # Determine language from majority of entries
        language = self._majority_language(entries)

        # Check if we already have a consolidation for this group
        existing = self._store.get_consolidation_by_group(
            location_id, category.value
        )

        entry_ids = [e.id for e in entries]

        if existing:
            # Update existing consolidation
            existing.summary = summary
            existing.entry_ids = entry_ids
            existing.entries_count = len(entries)
            existing.language = language
            existing.last_updated = datetime.now(timezone.utc)
            existing.version += 1
            return existing

        return ConsolidatedMemory(
            location_id=location_id,
            category=category,
            summary=summary,
            entry_ids=entry_ids,
            entries_count=len(entries),
            language=language,
        )

    def _build_summary(
        self, category: MemoryCategory, unique_contents: list[str]
    ) -> str:
        """
        Build a human-readable summary from unique contents.

        Different strategies per category for better readability.
        """
        if not unique_contents:
            return ""

        if len(unique_contents) == 1:
            return unique_contents[0][: self._max_summary_length]

        # For schedules, suppliers, and operational corrections,
        # bullet-point format works best
        if category in (
            MemoryCategory.SCHEDULES,
            MemoryCategory.SUPPLIERS,
            MemoryCategory.OPERATIONAL_CORRECTIONS,
        ):
            summary_parts: list[str] = []
            total_len = 0
            for idx, content in enumerate(unique_contents):
                bullet = f"• {content}"
                if total_len + len(bullet) + 1 > self._max_summary_length:
                    remaining = len(unique_contents) - idx
                    bullet = f"… y {remaining} más"
                    summary_parts.append(bullet)
                    break
                summary_parts.append(bullet)
                total_len += len(bullet) + 1
            return "\n".join(summary_parts)

        # For incidents and preferences, paragraph format
        if category in (
            MemoryCategory.KNOWN_INCIDENTS,
            MemoryCategory.COMMUNICATION_PREFERENCES,
        ):
            joined = " | ".join(unique_contents)
            if len(joined) > self._max_summary_length:
                joined = joined[: self._max_summary_length - 3] + "..."
            return joined

        # Default: comma-separated
        joined_default = ", ".join(unique_contents)
        if len(joined_default) > self._max_summary_length:
            joined_default = joined_default[: self._max_summary_length - 3] + "..."
        return joined_default

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _majority_language(entries: list[MemoryEntry]) -> str:
        """Determine the majority language from a list of entries."""
        lang_counts: dict[str, int] = {}
        for entry in entries:
            lang_counts[entry.language] = lang_counts.get(entry.language, 0) + 1

        if not lang_counts:
            return "es"

        return max(lang_counts, key=lang_counts.get)

    # ──────────────────────────────────────────
    # Deconsolidation (for when entries are deleted)
    # ──────────────────────────────────────────

    def deconsolidate_entry(self, entry_id: str) -> Optional[ConsolidatedMemory]:
        """
        Remove an entry from its consolidation group and rebuild the summary.

        Call this when an entry is soft-deleted.
        Returns the updated consolidation, or None if no group exists.
        """
        entry = self._store.get_entry(entry_id)
        if not entry:
            return None

        # Find consolidation for this group
        consolidation = self._store.get_consolidation_by_group(
            entry.location_id, entry.category.value
        )
        if not consolidation:
            return None

        # Remove entry from the group
        if entry_id in consolidation.entry_ids:
            consolidation.entry_ids.remove(entry_id)
            consolidation.entries_count = len(consolidation.entry_ids)

            # Rebuild summary from remaining entries
            remaining_entries = [
                self._store.get_entry(eid)
                for eid in consolidation.entry_ids
                if self._store.get_entry(eid)
            ]
            if remaining_entries:
                unique_contents = list(
                    dict.fromkeys(e.content.strip() for e in remaining_entries)
                )
                consolidation.summary = self._build_summary(
                    entry.category, unique_contents
                )
            else:
                # No entries left — mark as empty
                consolidation.summary = ""
                consolidation.entry_ids = []
                consolidation.entries_count = 0

            consolidation.last_updated = datetime.now(timezone.utc)
            consolidation.version += 1
            return self._store.save_consolidation(consolidation)

        return consolidation