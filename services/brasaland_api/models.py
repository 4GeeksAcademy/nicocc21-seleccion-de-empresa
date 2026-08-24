from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
