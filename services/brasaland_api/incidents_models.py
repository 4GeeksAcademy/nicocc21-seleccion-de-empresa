from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncidentOrigin(str, Enum):
    cliente = "cliente"
    interno = "interno"


class IncidentCategory(str, Enum):
    queja = "queja"
    solicitud = "solicitud"
    fallo_operativo = "fallo_operativo"


class IncidentState(str, Enum):
    abierta = "abierta"
    en_progreso = "en_progreso"
    resuelta = "resuelta"
    descartada = "descartada"


class IncidentPriority(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


VALID_LOCAL_IDS = {f"L{i:02d}" for i in range(1, 15)}

VALID_STATE_TRANSITIONS: dict[str, set[str]] = {
    "abierta": {"en_progreso", "descartada"},
    "en_progreso": {"resuelta", "descartada"},
    "resuelta": set(),
    "descartada": set(),
}


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    fecha_reporte: str
    local_id: str = Field(min_length=3, max_length=3)
    origen: IncidentOrigin
    categoria: IncidentCategory
    prioridad: IncidentPriority
    cliente_id: str | None = None
    cliente_email: str | None = None
    cliente_telefono: str | None = None

    @field_validator("local_id")
    @classmethod
    def validate_local_id(cls, v: str) -> str:
        if v not in VALID_LOCAL_IDS:
            raise ValueError(f"local_id debe ser uno de: {', '.join(sorted(VALID_LOCAL_IDS))}")
        return v

    @field_validator("fecha_reporte")
    @classmethod
    def validate_fecha(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("fecha_reporte debe tener formato ISO (YYYY-MM-DD)")
        return v


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    local_id: str | None = Field(default=None, min_length=3, max_length=3)
    origen: IncidentOrigin | None = None
    categoria: IncidentCategory | None = None
    prioridad: IncidentPriority | None = None
    cliente_id: str | None = None
    cliente_email: str | None = None
    cliente_telefono: str | None = None

    @field_validator("local_id")
    @classmethod
    def validate_local_id(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_LOCAL_IDS:
            raise ValueError(f"local_id debe ser uno de: {', '.join(sorted(VALID_LOCAL_IDS))}")
        return v


class IncidentStatusUpdate(BaseModel):
    estado: IncidentState


class IncidentOut(BaseModel):
    id: int
    incident_id: str
    title: str
    description: str
    fecha_reporte: str
    local_id: str
    origen: str
    categoria: str
    estado: str
    prioridad: str
    cliente_id: str | None
    cliente_email: str | None
    cliente_telefono: str | None
    satisfaccion: int | None
    created_at: str
    updated_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_incident_id(seq: int) -> str:
    return f"INC-{seq:04d}"