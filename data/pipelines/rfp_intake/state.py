"""Estado compartido del grafo rfp_intake.

Tipos Pydantic que definen el estado que fluye entre nodos del pipeline.
No confundir con los modelos ORM de rfp_models.py — esto es estado runtime
del grafo LangGraph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReadabilityMetrics:
    """Métricas de legibilidad del documento convertido a Markdown."""
    flesch_reading_ease: Optional[float] = None
    flesch_kincaid_grade: Optional[float] = None
    gunning_fog: Optional[float] = None
    word_count: Optional[int] = None
    sentence_count: Optional[int] = None


@dataclass
class RFPMetadata:
    """Metadatos extraídos del documento RFP."""
    client_name: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    scope: Optional[str] = None
    deadline: Optional[str] = None
    budget_range: Optional[str] = None
    budget_min_usd: Optional[float] = None
    budget_max_usd: Optional[float] = None
    departments_needed: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class DepartmentAnalysis:
    """Análisis realizado por el worker de un departamento."""
    department_id: str
    key_aspects: dict  # JSON serializable


@dataclass
class RFPIntakeState:
    """Estado completo del pipeline de recepción RFP.

    Atraviesa los nodos en orden:
      1. pdf_to_markdown   → markdown_content, readability, error
      2. classifier        → is_valid, rfp_metadata, error
      3. orchestrator      → rfp_metadata.departments_needed
      4. workers           → department_analyses[]
      5. synthesizer       → final_summary
    """
    # --- Entrada ---
    ticket_id: int
    pdf_path: str

    # --- Nodo 1: PDF → Markdown ---
    markdown_content: Optional[str] = None
    markdown_path: Optional[str] = None
    readability: Optional[ReadabilityMetrics] = None

    # --- Nodo 2: Clasificador ---
    is_valid: Optional[bool] = None
    rfp_metadata: Optional[RFPMetadata] = None

    # --- Nodos 3-4: Orquestador + Workers ---
    department_analyses: list[DepartmentAnalysis] = field(default_factory=list)

    # --- Nodo 5: Synthesizer ---
    final_summary: Optional[str] = None

    # --- Error handling ---
    error: Optional[str] = None
    error_node: Optional[str] = None