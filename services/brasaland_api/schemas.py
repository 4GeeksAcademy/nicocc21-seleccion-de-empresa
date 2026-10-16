"""Schemas Pydantic de request/response para el módulo de inventario (Hito 5).

Separados de los modelos ORM (SQLModel) en `inventory_models.py` — nunca se
devuelve un objeto ORM directamente desde un endpoint.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Tipos literales alineados con CONTEXT.md y src/hito2/types.ts
# ---------------------------------------------------------------------------

# Categorías de ingredientes definidas para Hito 5.
CategoriaInsumo = Literal["meat", "produce", "sauce", "beverage", "packaging", "cleaning"]

# Países donde opera Brasaland (14 locales: Colombia + Florida)
Pais = Literal["CO", "US"]

# Razones de salida de stock (consumo o merma).
RazonSalida = Literal["consumption", "waste"]

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
    location_id: int | None = None
    location_minimum_stock: float | None = None

# ---------------------------------------------------------------------------
# Movimientos de inventario — base compartida
# ---------------------------------------------------------------------------


class InventoryMovementBase(BaseModel):
    """Campos comunes de cualquier movimiento de inventario (entrada o salida).

    Existe para que la unión `list[IngredientEntryOut | IngredientExitOut]`
    de GET /inventory/orders comparta una proyección explícita y el campo
    `type` discrimine cada variante sin anidar el objeto `Ingredient`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    ingredient_name: str = Field(description="Nombre del insumo (join)")
    quantity: float
    location_id: int
    created_at: datetime
    user_uuid: str = Field(description="UUID del usuario que registró (del JWT)")
    telemetry_events: list[dict[str, object]] = Field(default_factory=list)
    telemetry_issues: list[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# IngredientEntry — orden de entrada (recibo de proveedor)
# ---------------------------------------------------------------------------


class IngredientEntryCreate(BaseModel):
    """Payload para registrar una recepción de mercancía de proveedor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ingredient_id: int = Field(description="ID del insumo recibido")
    quantity: float = Field(gt=0, allow_inf_nan=False, description="Cantidad recibida")
    supplier_name: str = Field(default="", description="Nombre historico del proveedor")
    supplier_id: int | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0, max_digits=22, decimal_places=2)
    currency: Literal["COP", "USD"] | None = None
    location_id: int = LocalId
    # user_uuid se extrae del JWT automáticamente — no se pide en el body

    @model_validator(mode="after")
    def validate_supplier(self) -> "IngredientEntryCreate":
        if self.supplier_id is None and not self.supplier_name.strip():
            raise ValueError("Se requiere un proveedor")
        complete_fields = (self.supplier_id, self.unit_price, self.currency)
        if any(value is not None for value in complete_fields) and not all(value is not None for value in complete_fields):
            raise ValueError("Proveedor, precio y moneda deben indicarse juntos")
        return self


class IngredientEntryOut(InventoryMovementBase):
    """Respuesta de una entrada de inventario."""

    supplier_name: str
    supplier_id: int | None = None
    unit_price: Decimal | None = None
    currency: str | None = None
    type: Literal["inbound"] = "inbound"


# ---------------------------------------------------------------------------
# IngredientExit — orden de salida (consumo o merma)
# ---------------------------------------------------------------------------


class IngredientExitCreate(BaseModel):
    """Payload para registrar consumo o merma de un insumo."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ingredient_id: int = Field(description="ID del insumo consumido")
    quantity: float = Field(gt=0, allow_inf_nan=False, description="Cantidad consumida/mermada")
    reason: RazonSalida
    waste_reason: Literal["expired", "kitchen_error", "theft_suspected"] | None = None
    minimum_stock: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    location_id: int = LocalId
    # user_uuid se extrae del JWT automáticamente

    @model_validator(mode="after")
    def validate_waste_reason(self) -> "IngredientExitCreate":
        if self.reason == "consumption" and self.waste_reason is not None:
            raise ValueError("El consumo no admite causa de merma")
        return self


class IngredientExitOut(InventoryMovementBase):
    """Respuesta de una salida de inventario."""

    reason: str
    waste_reason: str | None = None
    type: Literal["outbound"] = "outbound"
