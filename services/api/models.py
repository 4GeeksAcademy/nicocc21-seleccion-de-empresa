from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class Country(str, Enum):
    colombia = "Colombia"
    usa = "USA"


class Currency(str, Enum):
    cop = "COP"
    usd = "USD"


class SupplierStatus(str, Enum):
    active = "active"
    suspended = "suspended"


class SupplierCategory(str, Enum):
    carne = "carne"
    verduras_y_hortalizas = "verduras_y_hortalizas"
    salsas_y_condimentos = "salsas_y_condimentos"
    bebidas = "bebidas"
    packaging = "packaging"
    productos_limpieza = "productos_limpieza"
    lacteos = "lacteos"
    carbon_y_combustible = "carbon_y_combustible"


class SupplierBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)
    country: Country
    categories: list[SupplierCategory] = Field(min_length=1)
    rate_per_unit: float = Field(gt=0)
    currency: Currency
    status: SupplierStatus
    contact_email: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_country_currency(self) -> "SupplierBase":
        if self.country == Country.colombia and self.currency != Currency.cop:
            raise ValueError("Un proveedor de Colombia debe usar currency='COP'")
        if self.country == Country.usa and self.currency != Currency.usd:
            raise ValueError("Un proveedor de USA debe usar currency='USD'")
        return self


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdateRate(BaseModel):
    rate_per_unit: float = Field(gt=0)


class SupplierUpdateStatus(BaseModel):
    status: SupplierStatus


class SupplierOut(SupplierBase):
    id: int
    updated_at: datetime


# --- Auth / Users ---


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    user = "user"


class UserCreate(BaseModel):
    """Registro de usuario: credenciales + perfil opcional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=5)
    password: str = Field(min_length=6)
    # Campos opcionales de perfil inicial
    name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    address: str | None = None


class UserOut(BaseModel):
    """Respuesta sin contraseña."""

    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: str


class UserUpdate(BaseModel):
    """Actualizar credenciales — solo admin puede cambiar email/role."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str | None = Field(default=None, min_length=5)
    role: UserRole | None = None


class Token(BaseModel):
    """Respuesta del login."""

    access_token: str
    token_type: str = "bearer"


class UserMeProfile(BaseModel):
    """Datos de perfil embebidos en la respuesta /auth/me."""

    full_name: str
    phone: str | None = None
    address: str | None = None


class UserMeOut(BaseModel):
    """Respuesta de GET /auth/me: datos del usuario + perfil vinculado."""

    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: str
    profile: UserMeProfile | None = None


# --- Profiles ---


class ProfileCreate(BaseModel):
    """Crear perfil (nombre visible + datos de contacto)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1)
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    """Actualizar perfil — todos opcionales."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    address: str | None = None


class ProfileOut(BaseModel):
    """Respuesta de perfil."""

    id: int
    user_id: int
    full_name: str
    phone: str | None = None
    address: str | None = None
