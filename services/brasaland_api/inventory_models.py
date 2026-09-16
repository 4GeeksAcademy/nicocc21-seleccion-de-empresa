"""Modelos ORM de inventario — Hito 5 (SQLModel + Supabase/PostgreSQL).

Nota deliberada: este módulo NO usa `from __future__ import annotations`.
SQLModel resuelve las relaciones inspeccionando las anotaciones de tipo en
tiempo de definición de clase; con anotaciones diferidas (PEP 563) las
relaciones fallan al inicializar el mapper de SQLAlchemy.

current_stock NUNCA se almacena aqui: se deriva de
SUM(IngredientEntry.quantity) - SUM(IngredientExit.quantity).
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ingredient(SQLModel, table=True):
    """Insumo/producto de inventario de Brasaland.

    current_stock NUNCA se almacena aquí: se deriva dinámicamente como
    SUM(entries.quantity) - SUM(exits.quantity).

    Atributos de negocio (según CONTEXT.md):
      - perecedero + dias_vida_util: control de vencimiento
      - frecuencia_rotacion_dias: 7 (perecederos) | 15 (licores/bebidas)
    """

    __tablename__ = "ingredients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    sku: str = Field(unique=True, index=True)
    unit: str
    category: str
    country: str

    # --- Campos de negocio según CONTEXT.md ---
    stock_minimo: float = Field(default=0.0, alias="stockMinimo")
    perecedero: bool = Field(default=True, alias="perecedero")
    dias_vida_util: int = Field(default=7, alias="diasVidaUtil")
    frecuencia_rotacion_dias: int = Field(default=7, alias="frecuenciaRotacionDias")

    entries: List["IngredientEntry"] = Relationship(back_populates="ingredient")
    exits: List["IngredientExit"] = Relationship(back_populates="ingredient")


class IngredientEntry(SQLModel, table=True):
    """Entrega de ingredientes recibida de un proveedor (incrementa stock)."""

    __tablename__ = "ingredient_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    quantity: float
    supplier_name: str
    location_id: int
    created_at: datetime = Field(default_factory=_utc_now)
    user_uuid: str

    ingredient: Optional[Ingredient] = Relationship(back_populates="entries")


class IngredientExit(SQLModel, table=True):
    """Consumo o merma de ingredientes (reduce stock)."""

    __tablename__ = "ingredient_exits"

    id: Optional[int] = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", index=True)
    quantity: float
    reason: str
    location_id: int
    created_at: datetime = Field(default_factory=_utc_now)
    user_uuid: str

    ingredient: Optional[Ingredient] = Relationship(back_populates="exits")
