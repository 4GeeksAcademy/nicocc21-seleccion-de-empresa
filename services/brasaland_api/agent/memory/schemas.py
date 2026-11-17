"""
Pydantic models for the memory subsystem.

Defines the core data structures for episodic memory:
- MemoryEntry: approved and stored memory facts
- MemoryProposal: items pending user confirmation
- MemoryDecision: record of what the user decided
- ConsolidatedMemory: grouped summary by location + category
- EvaluationResult: auto-evaluator output
- ProposalClassification: classified user response
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class MemoryCategory(str, Enum):
    """Categories of memorable information per the company briefing."""

    SCHEDULES = "horarios"
    SUPPLIERS = "proveedores"
    KNOWN_INCIDENTS = "incidentes_conocidos"
    COMMUNICATION_PREFERENCES = "preferencias_comunicacion"
    OPERATIONAL_CORRECTIONS = "correcciones_operativas"
    OTHER = "otros"

    @classmethod
    def sensitive_categories(cls) -> set[str]:
        """Categories that should NEVER be proposed for memory."""
        return {"datos_personales", "nomina", "compensacion"}


class DecisionValue(str, Enum):
    """Possible user decisions on a memory proposal."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    AMBIGUOUS = "ambiguous"


class ProposalStatus(str, Enum):
    """Lifecycle status of a memory proposal."""

    PENDING = "pending"
    DECIDED = "decided"
    EXPIRED = "expired"


class MemorySource(str, Enum):
    """Who or what originated the memory."""

    USER_CORRECTION = "user_correction"
    AGENT_INFERENCE = "agent_inference"
    ESCALATION_RESOLUTION = "escalation_resolution"
    MANUAL = "manual"


# ──────────────────────────────────────────────
# Core models
# ──────────────────────────────────────────────


class EvaluationResult(BaseModel):
    """
    Output of the auto-evaluator.

    Determines whether an interaction fragment is worth
    proposing as a memory entry.
    """

    should_propose: bool = False
    category: Optional[MemoryCategory] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    source_text: str = ""

    @field_validator("confidence_score")
    @classmethod
    def confidence_must_be_valid(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class MemoryProposal(BaseModel):
    """
    A memory item proposed to the user for confirmation.

    The agent never writes directly — it proposes, the user decides.
    """

    id: str = Field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:12]}")
    location_id: str
    category: MemoryCategory
    content: str
    rationale: str = ""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: MemorySource = MemorySource.USER_CORRECTION
    source_interaction: str = ""  # The conversation text that triggered this
    proposed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ProposalStatus = ProposalStatus.PENDING
    expires_at: Optional[datetime] = None  # Auto-descarta si no se decide antes


class MemoryDecision(BaseModel):
    """
    Immutable record of a user's decision on a proposal.

    Per ticket #MEM-092: what was proposed, what the user decided,
    and when — never assume approval by silence.
    """

    id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
    proposal_id: str
    decision: DecisionValue
    edited_content: Optional[str] = None  # Only populated if decision == EDITED
    decided_by: str = ""  # User identifier
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    @model_validator(mode="after")
    def check_edited_content(self) -> "MemoryDecision":
        if self.decision == DecisionValue.EDITED and not self.edited_content:
            raise ValueError("edited_content is required when decision is EDITED")
        return self


class MemoryEntry(BaseModel):
    """
    A memory fact that has been proposed, accepted by the user,
    and consolidated into persistent storage.
    """

    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    location_id: str
    category: MemoryCategory
    content: str
    language: str = "es"  # "es" or "en"
    source: MemorySource = MemorySource.USER_CORRECTION
    source_interaction: str = ""
    decision_id: str = ""  # Links back to the MemoryDecision that approved it
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_days: Optional[int] = None  # None = no expiration
    is_active: bool = True  # Soft-delete support
    version: int = 1


class ConsolidatedMemory(BaseModel):
    """
    Grouped memory by location_id + category.

    Instead of storing every correction as a separate entry,
    consolidation summarises related facts.
    """

    id: str = Field(default_factory=lambda: f"con_{uuid.uuid4().hex[:12]}")
    location_id: str
    category: MemoryCategory
    summary: str = ""
    entry_ids: list[str] = Field(default_factory=list)
    entries_count: int = 0
    language: str = "es"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


# ──────────────────────────────────────────────
# Classification
# ──────────────────────────────────────────────


class ProposalClassification(BaseModel):
    """
    Classified user response against a pending proposal.

    Per ticket #MEM-092: if the classification cannot be determined
    with reasonable confidence, the proposal is DISCARDED.
    """

    proposal_id: str
    user_response_text: str
    classification: DecisionValue
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    classified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("confidence")
    @classmethod
    def require_reasonable_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# ──────────────────────────────────────────────
# Container for persistent store
# ──────────────────────────────────────────────


class MemoryStoreData(BaseModel):
    """Top-level structure for the JSON memory store file."""

    entries: dict[str, MemoryEntry] = Field(default_factory=dict)
    proposals: dict[str, MemoryProposal] = Field(default_factory=dict)
    decisions: dict[str, MemoryDecision] = Field(default_factory=dict)
    consolidations: dict[str, ConsolidatedMemory] = Field(default_factory=dict)
    last_consolidated: Optional[datetime] = None
    store_version: str = "1.0"