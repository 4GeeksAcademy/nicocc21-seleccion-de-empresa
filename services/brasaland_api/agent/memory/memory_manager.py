"""
Orchestrator for the memory subsystem.

Coordinates evaluation, proposal, decision processing,
storage, and context injection for the agent.

Flujo completo:
    1. Agent interaction occurs
    2. evaluate_and_propose() → evaluator checks if memorable
    3. If yes → proposer creates proposal + formats confirmation
    4. User responds → process_decision() classifies + records
    5. If accepted → save as MemoryEntry + consolidate
    6. Next agent call → get_context() injects relevant memories
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .memory_consolidator import MemoryConsolidator
from .memory_evaluator import MemoryEvaluator
from .memory_proposer import MemoryProposer
from .memory_store import MemoryStore
from .schemas import (
    ConsolidatedMemory,
    DecisionValue,
    EvaluationResult,
    MemoryCategory,
    MemoryDecision,
    MemoryEntry,
    MemoryProposal,
    MemorySource,
    ProposalClassification,
    ProposalStatus,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# MemoryManager
# ──────────────────────────────────────────────


class MemoryManager:
    """
    Orchestrator for the memory subsystem.

    This is the main entry point for the agent to interact with memory.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        evaluator: Optional[MemoryEvaluator] = None,
        proposer: Optional[MemoryProposer] = None,
        consolidator: Optional[MemoryConsolidator] = None,
    ):
        self._store = store or MemoryStore()
        self._evaluator = evaluator or MemoryEvaluator()
        self._proposer = proposer or MemoryProposer()
        self._consolidator = consolidator or MemoryConsolidator(self._store)

        # Track pending proposals — limited to ONE at a time
        self._pending_proposal: MemoryProposal | None = None

    # ──────────────────────────────────────────
    # Main flow: evaluate and propose
    # ──────────────────────────────────────────

    def evaluate_and_propose(
        self,
        interaction_text: str,
        location_id: str,
        language: str = "es",
    ) -> tuple[Optional[MemoryProposal], Optional[str]]:
        """
        Evaluate an interaction and, if memorable, create a proposal.

        This is the core flow:
        1. Evaluate the interaction text
        2. If should_propose → create MemoryProposal
        3. Format confirmation prompt for the user

        Args:
            interaction_text: The conversation text to evaluate.
            location_id: Location context.
            language: Language for the confirmation prompt.

        Returns:
            Tuple of (MemoryProposal or None, confirmation_prompt or None).
            If None, None — nothing memorable was detected.
        """
        # Step 1: Check if there's already a pending proposal (limit to ONE)
        if self._pending_proposal is not None:
            logger.debug(
                "A pending proposal already exists (%s) — skipping new proposal",
                self._pending_proposal.id,
            )
            return None, None

        # Step 2: Evaluate
        evaluation = self._evaluator.evaluate(interaction_text, location_id)

        if not evaluation.should_propose:
            logger.debug(
                "Evaluation did not propose memory for location %s: %s",
                location_id,
                evaluation.rationale,
            )
            return None, None

        # Step 3: Create proposal
        proposal = self._proposer.create_proposal(
            location_id=location_id,
            category=evaluation.category or MemoryCategory.OTHER,
            content=self._extract_memorable_content(interaction_text, evaluation),
            rationale=evaluation.rationale,
            confidence_score=evaluation.confidence_score,
            source=MemorySource.USER_CORRECTION,
            source_interaction=interaction_text[:500],
        )

        # Step 4 (prev): Save proposal to store
        self._store.save_proposal(proposal)

        # Step 4: Track in-memory for quick lookup (only ONE at a time)
        self._pending_proposal = proposal

        # Step 5: Format confirmation prompt
        prompt = self._proposer.format_confirmation_prompt(proposal, language)

        logger.info(
            "Created proposal %s for location %s (category=%s, confidence=%.2f)",
            proposal.id,
            location_id,
            evaluation.category.value if evaluation.category else "unknown",
            evaluation.confidence_score,
        )

        return proposal, prompt

    # ──────────────────────────────────────────
    # Process user decision
    # ──────────────────────────────────────────

    def process_decision(
        self,
        proposal_id: str,
        user_response: str,
        decided_by: str = "",
        language: str = "es",
        edited_content: Optional[str] = None,
    ) -> tuple[MemoryDecision, Optional[MemoryEntry]]:
        """
        Process a user's response to a pending proposal.

        Per ticket #MEM-092:
        - Classifies the response explicitly
        - Records the decision (always, even if rejected)
        - If accepted → creates MemoryEntry + triggers consolidation
        - If rejected → discards proposal, but decision remains recorded
        - If ambiguous → defaults to rejected

        Args:
            proposal_id: The ID of the pending proposal.
            user_response: The user's text response.
            decided_by: Optional user identifier.
            language: Language for classification.
            edited_content: If the user edited the content, the corrected
                version. Passed through to record_decision.

        Returns:
            Tuple of (MemoryDecision, MemoryEntry or None).
            MemoryEntry is None if the proposal was rejected/ambiguous.
        """
        # Get proposal
        proposal = self._store.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        # Check if proposal is still pending
        if proposal.status != ProposalStatus.PENDING:
            raise ValueError(
                f"Proposal {proposal_id} is already {proposal.status.value}."
            )

        # Check expiration
        now = datetime.now(timezone.utc)
        if proposal.expires_at and proposal.expires_at < now:
            proposal.status = ProposalStatus.EXPIRED
            self._store.save_proposal(proposal)
            raise ValueError(f"Proposal {proposal_id} has expired.")

        # Classify response
        classification = self._proposer.classify_response(
            proposal, user_response, language
        )

        # Record decision (creates MemoryDecision, updates proposal status)
        decision = self._proposer.record_decision(
            proposal=proposal,
            classification=classification,
            decided_by=decided_by,
            edited_content=edited_content,
        )

        # Save decision to store
        decision = self._store.save_decision(decision)
        self._store.save_proposal(proposal)

        # Clean up pending tracking (only ONE at a time)
        self._pending_proposal = None

        # If accepted or edited → create MemoryEntry
        entry: Optional[MemoryEntry] = None
        if decision.decision in (DecisionValue.ACCEPTED, DecisionValue.EDITED):
            content = (
                decision.edited_content
                if decision.decision == DecisionValue.EDITED
                else proposal.content
            )
            entry = MemoryEntry(
                location_id=proposal.location_id,
                category=proposal.category,
                content=content,
                language=language,
                source=proposal.source,
                source_interaction=proposal.source_interaction,
                decision_id=decision.id,
            )
            entry = self._store.save_entry(entry)

            # Trigger consolidation for this location + category
            try:
                self._consolidator.consolidate_location(proposal.location_id)
            except Exception as exc:
                logger.warning(
                    "Consolidation after decision failed (non-fatal): %s", exc
                )

            logger.info(
                "Proposal %s ACCEPTED → created entry %s for location %s",
                proposal_id,
                entry.id,
                proposal.location_id,
            )
        else:
            logger.info(
                "Proposal %s %s — no entry created (decision recorded as %s).",
                proposal_id,
                decision.decision.value,
                decision.id,
            )

        return decision, entry

    # ──────────────────────────────────────────
    # Context injection for agent
    # ──────────────────────────────────────────

    def get_context(
        self,
        location_id: str,
        categories: Optional[list[MemoryCategory]] = None,
        include_consolidated: bool = True,
    ) -> str:
        """
        Build a context string for the agent prompt.

        Injects relevant memories for a given location, grouped
        by category. Returns a formatted string ready to insert
        into the system prompt or agent context.

        When using consolidated view (default), falls back to raw
        entries if no consolidations exist yet for the location.

        Args:
            location_id: The location to get context for.
            categories: Optional filter — only return these categories.
            include_consolidated: If True, prefer consolidated summaries
                                  but fall back to raw entries.

        Returns:
            Formatted string with relevant memories, or empty string.
        """
        parts: list[str] = []

        if include_consolidated:
            # Try consolidated summaries first
            consolidations = self._store.get_consolidations_for_location(location_id)
            if categories:
                consolidations = [
                    c for c in consolidations if c.category in categories
                ]

            if consolidations:
                for con in consolidations:
                    if con.summary:
                        label = self._category_label(con.category, con.language)
                        parts.append(f"[{label}] {con.summary}")
                # Use consolidations — done
                return self._format_context(location_id, parts)

        # Fall back to raw entries (either include_consolidated=False,
        # or no consolidations exist yet for this location)
        entries = self._store.get_entries(
            location_id=location_id, active_only=True
        )
        if categories:
            entries = [e for e in entries if e.category in categories]

        seen = set()
        for entry in entries:
            key = entry.content.strip().lower()
            if key not in seen:
                seen.add(key)
                label = self._category_label(entry.category, entry.language)
                parts.append(f"[{label}] {entry.content.strip()}")

        return self._format_context(location_id, parts)

    @staticmethod
    def _format_context(location_id: str, parts: list[str]) -> str:
        """Format context parts into a final string."""
        if not parts:
            return ""
        header = f"🧠 Memoria de location {location_id}:"
        return header + "\n" + "\n".join(f"  {p}" for p in parts)

    # ──────────────────────────────────────────
    # Consolidation helpers
    # ──────────────────────────────────────────

    def consolidate_all(self) -> list[ConsolidatedMemory]:
        """Trigger consolidation for all locations."""
        return self._consolidator.consolidate_all()

    def consolidate_location(self, location_id: str) -> list[ConsolidatedMemory]:
        """Trigger consolidation for a specific location."""
        return self._consolidator.consolidate_location(location_id)

    # ──────────────────────────────────────────
    # Query helpers
    # ──────────────────────────────────────────

    def get_pending_proposals(
        self, location_id: Optional[str] = None
    ) -> list[MemoryProposal]:
        """Get all pending (non-expired) proposals."""
        return self._store.get_pending_proposals(location_id)

    def get_store_info(self) -> dict:
        """Get summary info about the memory store."""
        return self._store.store_info()

    def search_memories(
        self,
        query: str,
        location_id: Optional[str] = None,
    ) -> list[MemoryEntry]:
        """Search memory entries by text content."""
        return self._store.search_entries(query, location_id)

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _extract_memorable_content(
        self, interaction_text: str, evaluation: EvaluationResult
    ) -> str:
        """
        Extract the memorable portion from interaction text.

        For the MVP, returns the source_text from the evaluation
        (first 200 chars). In production, this could use LLM
        summarisation.
        """
        # Use the source text from evaluation (already truncated to 200)
        source = evaluation.source_text.strip()
        if source:
            return source
        # Fallback: first 200 chars of interaction
        return interaction_text.strip()[:200]

    @staticmethod
    def _category_label(category: MemoryCategory, language: str) -> str:
        """Get a human-readable label for a memory category."""
        labels = {
            "es": {
                MemoryCategory.SCHEDULES: "Horarios",
                MemoryCategory.SUPPLIERS: "Proveedores",
                MemoryCategory.KNOWN_INCIDENTS: "Incidentes conocidos",
                MemoryCategory.COMMUNICATION_PREFERENCES: "Preferencias",
                MemoryCategory.OPERATIONAL_CORRECTIONS: "Correcciones operativas",
                MemoryCategory.OTHER: "Otros",
            },
            "en": {
                MemoryCategory.SCHEDULES: "Schedules",
                MemoryCategory.SUPPLIERS: "Suppliers",
                MemoryCategory.KNOWN_INCIDENTS: "Known incidents",
                MemoryCategory.COMMUNICATION_PREFERENCES: "Preferences",
                MemoryCategory.OPERATIONAL_CORRECTIONS: "Operational corrections",
                MemoryCategory.OTHER: "Other",
            },
        }
        return labels.get(language, labels["es"]).get(category, category.value)