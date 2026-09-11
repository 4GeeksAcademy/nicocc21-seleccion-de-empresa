"""Schemas Pydantic de request/response para el módulo de inventario (Hito 5).

Separados de los modelos ORM (SQLModel) en `inventory_models.py` — nunca se
devuelve un objeto ORM directamente desde un endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Tipos literales alineados con CONTEXT.md y src/hito2/types.ts
# ---------------------------------------------------------------------------

# CategoriaInsumo del dominio Brasaland
CategoriaInsumo = Literal["comida", "bebida", "empaque"]

# Países donde opera Brasaland (14 locales: Colombia + Florida)
Pais = Literal["CO", "US"]

# Razones de salida de stock (consumo o merma)
RazonSalida = Literal["consumo", "merma"]

# Locales: 1-14
LocalId = Field(ge=1, le=14)

# ---------------------------------------------------------------------------
# Ingredient (Insumo)
# ---------------------------------------------------------------------------


class IngredientCreate(BaseModel):
    """Payload para crear un insumo en el inventario de Brasaland."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Nombre del insumo (ej. 'Lomo fino')")
    sku: str = Field(min_length=1, description="Código SKU único del insumo")
    unit: str = Field(min_length=1, description="Unidad de medida (kg, L, und)")
    category: CategoriaInsumo
    country: Pais
    stock_minimo: float = Field(
        default=0.0, ge=0, description="Stock mínimo antes de generar alerta"
    )
    perecedero: bool = Field(default=True, description="¿Es perecedero?")
    dias_vida_util: int = Field(
        default=7, ge=1, description="Días de vida útil desde recepción"
    )
    frecuencia_rotacion_dias: int = Field(
        default=7, ge=1, description="Ciclo de rotación esperado (7=perecedero, 15=bebidas)"
    )


class IngredientOut(BaseModel):
    """Respuesta de insumo, incluye current_stock calculado dinámicamente."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    sku: str
    unit: str
    category: str
    country: str
    stock_minimo: float
    perecedero: bool
    dias_vida_util: int
    frecuencia_rotacion_dias: int
    current_stock: float

# ---------------------------------------------------------------------------
# IngredientEntry — orden de entrada (recibo de proveedor)
# ---------------------------------------------------------------------------


class IngredientEntryCreate(BaseModel):
    """Payload para registrar una recepción de mercancía de proveedor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ingredient_id: int = Field(description="ID del insumo recibido")
    quantity: float = Field(gt=0, description="Cantidad recibida")
    supplier_name: str = Field(min_length=1, description="Nombre del proveedor")
    location_id: int = LocalId
    # user_uuid se extrae del JWT automáticamente — no se pide en el body


class IngredientEntryOut(BaseModel):
    """Respuesta de una entrada de inventario."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    ingredient_name: str = Field(description="Nombre del insumo (join)")
    quantity: float
    supplier_name: str
    location_id: int
    created_at: datetime
    user_uuid: str = Field(description="UUID del usuario que registró (del JWT)")
    type: Literal["inbound"] = "inbound"


# ---------------------------------------------------------------------------
# IngredientExit — orden de salida (consumo o merma)
# ---------------------------------------------------------------------------


class IngredientExitCreate(BaseModel):
    """Payload para registrar consumo o merma de un insumo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ingredient_id: int = Field(description="ID del insumo consumido")
    quantity: float = Field(gt=0, description="Cantidad consumida/mermada")
    reason: RazonSalida
    location_id: int = LocalId
    # user_uuid se extrae del JWT automáticamente


class IngredientExitOut(BaseModel):
    """Respuesta de una salida de inventario."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    ingredient_name: str
    quantity: float
    reason: str
    location_id: int
    created_at: datetime
    user_uuid: str
    type: Literal["outbound"] = "outbound"
