"""
Persistent storage for memory entries, proposals, and decisions.

JSON-based local store under data/memory/. Supports CRUD,
search by location/category/text, and bilingual content.

Structure:
    data/memory/
        memory_store.json          # Main store file
        proposals.json             # Pending proposals
        decisions.json             # Decision audit log
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from .schemas import (
    ConsolidatedMemory,
    DecisionValue,
    MemoryDecision,
    MemoryEntry,
    MemoryProposal,
    MemoryStoreData,
    ProposalStatus,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Store class
# ──────────────────────────────────────────────


class MemoryStore:
    """
    Persistent JSON-based store for the memory subsystem.

    Thread-safe via Lock. All write operations flush to disk immediately.
    """

    def __init__(self, store_dir: str | Path = "data/memory"):
        self._store_dir = Path(store_dir)
        self._store_file = self._store_dir / "memory_store.json"
        self._lock = Lock()

        # In-memory cache
        self._data: MemoryStoreData = MemoryStoreData()

        # Ensure directory exists
        self._store_dir.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load()

    # ──────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────

    def _load(self) -> None:
        """Load store data from disk."""
        if not self._store_file.exists():
            logger.info("No existing store file at %s — starting fresh.", self._store_file)
            self._data = MemoryStoreData()
            self._save()
            return

        try:
            with open(self._store_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._data = MemoryStoreData.model_validate(raw)
            logger.info(
                "Loaded memory store: %d entries, %d proposals, %d decisions, %d consolidations",
                len(self._data.entries),
                len(self._data.proposals),
                len(self._data.decisions),
                len(self._data.consolidations),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to load store file, starting fresh: %s", exc)
            self._data = MemoryStoreData()
            self._save()

    def _save(self) -> None:
        """Write store data to disk atomically."""
        tmp = self._store_file.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    self._data.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            tmp.replace(self._store_file)
        except Exception as exc:
            logger.error("Failed to save memory store: %s", exc)
            raise

    # ──────────────────────────────────────────
    # Entries CRUD
    # ──────────────────────────────────────────

    def save_entry(self, entry: MemoryEntry) -> MemoryEntry:
        """Save a new memory entry or update an existing one."""
        with self._lock:
            entry.updated_at = datetime.now(timezone.utc)
            if entry.id in self._data.entries:
                entry.version = self._data.entries[entry.id].version + 1
            self._data.entries[entry.id] = entry
            self._save()
        return entry

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        return self._data.entries.get(entry_id)

    def get_entries(
        self,
        location_id: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[MemoryEntry]:
        """
        Retrieve entries with optional filters.

        Args:
            location_id: Filter by location.
            category: Filter by category string.
            active_only: Only return active (not soft-deleted) entries.

        Returns:
            List of matching MemoryEntry objects, ordered by created_at desc.
        """
        result = []
        for entry in self._data.entries.values():
            if active_only and not entry.is_active:
                continue
            if location_id and entry.location_id != location_id:
                continue
            if category and entry.category.value != category:
                continue
            result.append(entry)

        result.sort(key=lambda e: e.created_at, reverse=True)
        return result

    def soft_delete_entry(self, entry_id: str) -> bool:
        """Soft-delete a memory entry (mark as inactive)."""
        with self._lock:
            entry = self._data.entries.get(entry_id)
            if not entry:
                return False
            entry.is_active = False
            entry.updated_at = datetime.now(timezone.utc)
            self._save()
        return True

    def hard_delete_entry(self, entry_id: str) -> bool:
        """Permanently remove a memory entry."""
        with self._lock:
            if entry_id not in self._data.entries:
                return False
            del self._data.entries[entry_id]
            self._save()
        return True

    # ──────────────────────────────────────────
    # Proposals CRUD
    # ──────────────────────────────────────────

    def save_proposal(self, proposal: MemoryProposal) -> MemoryProposal:
        """Save a new proposal or update an existing one."""
        with self._lock:
            self._data.proposals[proposal.id] = proposal
            self._save()
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[MemoryProposal]:
        """Retrieve a proposal by ID."""
        return self._data.proposals.get(proposal_id)

    def get_pending_proposals(
        self, location_id: Optional[str] = None
    ) -> list[MemoryProposal]:
        """
        Get all pending (undecided, non-expired) proposals.

        Automatically expires proposals past their TTL.
        """
        now = datetime.now(timezone.utc)
        pending = []
        expired_ids = []

        for pid, prop in self._data.proposals.items():
            if prop.status != ProposalStatus.PENDING:
                continue
            # Check expiration
            if prop.expires_at and prop.expires_at < now:
                prop.status = ProposalStatus.EXPIRED
                expired_ids.append(pid)
                continue
            # Filter by location
            if location_id and prop.location_id != location_id:
                continue
            pending.append(prop)

        # Save expired status changes
        if expired_ids:
            with self._lock:
                self._save()

        return pending

    def update_proposal_status(
        self, proposal_id: str, status: ProposalStatus
    ) -> bool:
        """Update the status of a proposal."""
        with self._lock:
            prop = self._data.proposals.get(proposal_id)
            if not prop:
                return False
            prop.status = status
            self._save()
        return True

    # ──────────────────────────────────────────
    # Decisions CRUD
    # ──────────────────────────────────────────

    def save_decision(self, decision: MemoryDecision) -> MemoryDecision:
        """Save a decision record (immutable — no updates allowed)."""
        with self._lock:
            if decision.id in self._data.decisions:
                raise ValueError(
                    f"Decision {decision.id} already exists and is immutable."
                )
            self._data.decisions[decision.id] = decision
            self._save()
        return decision

    def get_decision(self, decision_id: str) -> Optional[MemoryDecision]:
        """Retrieve a decision by ID."""
        return self._data.decisions.get(decision_id)

    def get_decisions_for_proposal(
        self, proposal_id: str
    ) -> list[MemoryDecision]:
        """Get all decisions associated with a proposal."""
        return [
            d
            for d in self._data.decisions.values()
            if d.proposal_id == proposal_id
        ]

    def get_decisions(
        self,
        location_id: Optional[str] = None,
        decision_type: Optional[DecisionValue] = None,
        limit: int = 50,
    ) -> list[MemoryDecision]:
        """
        Get decisions with optional filters.

        Links through proposals to find location-specific decisions.
        """
        result = []
        for dec in self._data.decisions.values():
            if decision_type and dec.decision != decision_type:
                continue
            if location_id:
                prop = self._data.proposals.get(dec.proposal_id)
                if not prop or prop.location_id != location_id:
                    continue
            result.append(dec)

        result.sort(key=lambda d: d.decided_at, reverse=True)
        return result[:limit]

    # ──────────────────────────────────────────
    # Consolidations CRUD
    # ──────────────────────────────────────────

    def save_consolidation(
        self, consolidation: ConsolidatedMemory
    ) -> ConsolidatedMemory:
        """Save or update a consolidation record."""
        with self._lock:
            consolidation.last_updated = datetime.now(timezone.utc)
            self._data.consolidations[consolidation.id] = consolidation
            self._save()
        return consolidation

    def get_consolidation(self, consolidation_id: str) -> Optional[ConsolidatedMemory]:
        """Retrieve a consolidation by ID."""
        return self._data.consolidations.get(consolidation_id)

    def get_consolidations_for_location(
        self, location_id: str
    ) -> list[ConsolidatedMemory]:
        """Get all consolidations for a specific location."""
        return [
            c
            for c in self._data.consolidations.values()
            if c.location_id == location_id
        ]

    def get_consolidation_by_group(
        self, location_id: str, category: str
    ) -> Optional[ConsolidatedMemory]:
        """Get the consolidation for a specific location + category group."""
        for c in self._data.consolidations.values():
            if c.location_id == location_id and c.category.value == category:
                return c
        return None

    # ──────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────

    def search_entries(
        self,
        query: str,
        location_id: Optional[str] = None,
        max_results: int = 20,
    ) -> list[MemoryEntry]:
        """
        Simple text search across active memory entries.

        Searches content field. Case-insensitive.
        Supports bilingual content (Spanish/English).
        """
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        results = []
        for entry in self._data.entries.values():
            if not entry.is_active:
                continue
            if location_id and entry.location_id != location_id:
                continue
            if query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:max_results]

    # ──────────────────────────────────────────
    # Stats / Info
    # ──────────────────────────────────────────

    def count_entries(
        self, location_id: Optional[str] = None, active_only: bool = True
    ) -> int:
        """Count entries with optional filters."""
        count = 0
        for entry in self._data.entries.values():
            if active_only and not entry.is_active:
                continue
            if location_id and entry.location_id != location_id:
                continue
            count += 1
        return count

    def store_info(self) -> dict:
        """Get summary info about the store contents."""
        return {
            "total_entries": len(self._data.entries),
            "active_entries": self.count_entries(),
            "total_proposals": len(self._data.proposals),
            "pending_proposals": len(self.get_pending_proposals()),
            "total_decisions": len(self._data.decisions),
            "total_consolidations": len(self._data.consolidations),
            "last_consolidated": (
                self._data.last_consolidated.isoformat()
                if self._data.last_consolidated
                else None
            ),
            "store_version": self._data.store_version,
        }

    def get_all_location_ids(self) -> list[str]:
        """Get a list of all location IDs that have memory entries."""
        locs = set()
        for entry in self._data.entries.values():
            if entry.is_active:
                locs.add(entry.location_id)
        return sorted(locs)