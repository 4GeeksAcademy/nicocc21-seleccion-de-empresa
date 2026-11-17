"""Modelos ORM del flujo de RFPs — Hito 9 (SQLModel + Supabase/PostgreSQL).

NOTA: Sin `from __future__ import annotations`. SQLModel necesita las
anotaciones de tipo en tiempo de definición de clase para el mapper.

Estos modelos persisten en las tablas:
  - rfp_tickets         → ciclo de vida del ticket
  - rfp_metadata        → metadatos extraídos del documento
  - rfp_department_sections → aspectos clave por departamento (Parte 1)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Ticket ────────────────────────────────────────────────────────────

class Ticket(SQLModel, table=True):
    """Ticket de recepción de RFP.

    Cada subida de PDF genera un ticket con su propio ciclo de vida.
    El mismo ticket continúa en Partes 2 y 3.
    """

    __tablename__ = "rfp_tickets"

    id: Optional[int] = Field(default=None, primary_key=True)
    rfp_external_id: Optional[str] = Field(
        default=None, max_length=128,
        description="Identificador externo opcional (ej. número de referencia del cliente)",
    )
    status: str = Field(
        default="analizando", max_length=32,
        description=(
            "Estados válidos Parte 1: analizando, descartado, analisis_completo. "
            "Partes 2-3 añaden: generando_borrador, en_evaluacion, "
            "needs_human_review, esperando_aprobacion, terminado"
        ),
    )
    raw_pdf_path: str = Field(
        default="", max_length=512,
        description="Ruta relativa al PDF original bajo data/raw/",
    )
    markdown_path: Optional[str] = Field(
        default=None, max_length=512,
        description="Ruta relativa al Markdown convertido bajo data/raw/",
    )
    error_message: Optional[str] = Field(
        default=None, sa_type=Text,
        description="Si el pipeline falló, mensaje de error",
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now, sa_column_kwargs={"onupdate": _utc_now})


# ─── RFP Metadata ──────────────────────────────────────────────────────

class RFPMetadata(SQLModel, table=True):
    """Metadatos extraídos del documento RFP por el clasificador/orquestador."""

    __tablename__ = "rfp_metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="rfp_tickets.id", index=True, unique=True)

    # --- Metadatos del documento ---
    client_name: Optional[str] = Field(default=None, max_length=256)
    location: Optional[str] = Field(default=None, max_length=256)
    service_type: Optional[str] = Field(default=None, max_length=128)
    scope: Optional[str] = Field(default=None, sa_type=Text)
    deadline: Optional[str] = Field(default=None, max_length=64)
    budget_range: Optional[str] = Field(default=None, max_length=128)
    budget_min_usd: Optional[float] = Field(default=None)
    budget_max_usd: Optional[float] = Field(default=None)
    departments_needed: str = Field(
        default="", max_length=256,
        description="Lista JSON de department_ids necesarios, ej. [\"marketing\",\"operaciones\"]",
    )

    # --- Métricas de legibilidad ---
    flesch_reading_ease: Optional[float] = Field(default=None)
    flesch_kincaid_grade: Optional[float] = Field(default=None)
    gunning_fog: Optional[float] = Field(default=None)
    word_count: Optional[int] = Field(default=None)
    sentence_count: Optional[int] = Field(default=None)

    # --- Control ---
    created_at: datetime = Field(default_factory=_utc_now)


# ─── Department Section (key_aspects Parte 1) ─────────────────────────

class DepartmentSection(SQLModel, table=True):
    """Aspectos clave extraídos por el worker de cada departamento.

    En la Parte 1 solo se usa `key_aspects`. Las Partes 2-3 añadirán
    draft_content, evaluation_results, approval_status, approver, approved_at.
    """

    __tablename__ = "rfp_department_sections"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="rfp_tickets.id", index=True)
    department_id: str = Field(max_length=32, index=True)

    # --- Parte 1 ---
    key_aspects: Optional[str] = Field(
        default=None, sa_type=Text,
        description="JSON con aspectos clave relevantes para este departamento",
    )

    # --- Parte 2 (futuro) ---
    draft_content: Optional[str] = Field(default=None, sa_type=Text)
    evaluation_results: Optional[dict] = Field(
        default=None, sa_type=JSON,
        description="Resultados de evaluación: legibilidad, pertinencia, cumplimiento",
    )

    # --- Parte 3 (futuro) ---
    approval_status: str = Field(
        default="pendiente", max_length=32,
        description="pendiente | aprobado | rechazado | request_changes",
    )
    approver: Optional[str] = Field(default=None, max_length=128)
    approved_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now, sa_column_kwargs={"onupdate": _utc_now})

    class UniqueConstraint:
        __table_args__ = (
            {"sqlite_autoincrement": True},  # compatibilidad
        )


# ─── Helpers ───────────────────────────────────────────────────────────

def ensure_rfp_tables() -> None:
    """Crea las tablas de RFP en la base de datos si no existen.

    Debe llamarse desde el lifespan de la aplicación o desde un script de
    migración. Reutiliza el engine definido en database.py.
    """
    from services.brasaland_api.database import engine
    SQLModel.metadata.create_all(engine, tables=[
        Ticket.__table__,
        RFPMetadata.__table__,
        DepartmentSection.__table__,
    ])