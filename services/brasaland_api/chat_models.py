"""Modelos ORM del chat en tiempo real (WebSocket) — Hito 9, Parte 2.

Sigue la misma convención que rfp_models.py:
- Sin `from __future__ import annotations` (SQLModel necesita anotaciones en tiempo real)
- SQLModel + Supabase/PostgreSQL
- `ensure_chat_tables()` para crear tablas al arrancar

Tablas:
  - chat_sessions → sesión activa de chat con el support agent
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid4())


# ─── Chat Session ──────────────────────────────────────────────────────

class ChatSession(SQLModel, table=True):
    """Sesión de chat con el Manager Support Agent.

    Una sesión comienza cuando el encargado de local se conecta al WebSocket
    y permanece activa hasta que se cierra explícitamente o expira.

    El `session_id` se usa también como `thread_id` de LangGraph para
    rehidratar la conversación al reconectar.
    """

    __tablename__ = "chat_sessions"

    session_id: str = Field(
        default_factory=_new_uuid, primary_key=True, max_length=36,
        description="UUID único de la sesión. También se usa como LangGraph thread_id",
    )
    agent_id: str = Field(
        default="manager_support", max_length=64,
        description="Identificador del agente (siempre 'manager_support')",
    )
    user_id: Optional[int] = Field(
        default=None, foreign_key="users.id",
        description="ID del usuario (encargado de local) que chatea",
    )
    location_id: Optional[str] = Field(
        default=None, max_length=16,
        description="Local de Brasaland asociado (ej. L01, L02, ..., L14)",
    )
    status: str = Field(
        default="active", max_length=32,
        description="active | interrupted | closed",
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now, sa_column_kwargs={"onupdate": _utc_now})


# ─── Helpers ───────────────────────────────────────────────────────────

def ensure_chat_tables() -> None:
    """Crea las tablas de chat en la base de datos si no existen.

    Debe llamarse desde el lifespan de la aplicación.
    Reutiliza el engine definido en database.py.
    """
    from services.brasaland_api.database import engine
    SQLModel.metadata.create_all(engine, tables=[
        ChatSession.__table__,
    ])