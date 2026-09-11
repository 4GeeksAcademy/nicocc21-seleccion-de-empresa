#!/usr/bin/env python3
"""Seeder de inventario — Hito 5 (Brasaland).

Idempotente: si ya existen ingredientes en Supabase, no vuelve a insertar.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from sqlmodel import Session, select

from services.brasaland_api.database import create_db_and_tables, engine
from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit
from services.brasaland_api.inventory_seed_data import (
    INGREDIENT_ENTRIES_SEED,
    INGREDIENT_EXITS_SEED,
    INGREDIENTS_SEED,
)


def run_inventory_seed(verbose: bool = True) -> tuple[int, int, int]:
    create_db_and_tables()

    with Session(engine) as session:
        existing_count = len(session.exec(select(Ingredient)).all())
        if existing_count > 0:
            if verbose:
                print(f"Seed de inventario omitido: ya existen {existing_count} ingredientes")
            return 0, existing_count, len(INGREDIENTS_SEED)

        sku_to_id: dict[str, int] = {}
        for payload in INGREDIENTS_SEED:
            ingredient = Ingredient(**payload)
            session.add(ingredient)
            session.flush()  # asigna ingredient.id sin hacer commit todavia
            sku_to_id[ingredient.sku] = ingredient.id

        for payload in INGREDIENT_ENTRIES_SEED:
            sku = payload["sku"]
            entry_data = {k: v for k, v in payload.items() if k != "sku"}
            session.add(
                IngredientEntry(ingredient_id=sku_to_id[sku], **entry_data)
            )

        for payload in INGREDIENT_EXITS_SEED:
            sku = payload["sku"]
            exit_data = {k: v for k, v in payload.items() if k != "sku"}
            session.add(
                IngredientExit(ingredient_id=sku_to_id[sku], **exit_data)
            )

        session.commit()

    inserted = len(INGREDIENTS_SEED)

    if verbose:
        print("Seeder de inventario completado")
        print(f"Ingredientes insertados: {inserted}")
        print(f"Entradas insertadas: {len(INGREDIENT_ENTRIES_SEED)}")
        print(f"Salidas insertadas: {len(INGREDIENT_EXITS_SEED)}")

    return inserted, 0, inserted


if __name__ == "__main__":
    run_inventory_seed(verbose=True)
