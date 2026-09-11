#!/usr/bin/env python3
"""Drop y recreate tablas de inventario en Supabase.

Útil cuando se añaden/modifican columnas en los modelos ORM.
Ejecutar antes de reiniciar la API para que `create_all` reconstruya.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[1] / "services" / "brasaland_api" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from sqlmodel import SQLModel
from services.brasaland_api.database import engine
from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit

if __name__ == "__main__":
    print("Dropping old tables...")
    SQLModel.metadata.drop_all(engine)
    print("Creating tables with new schema...")
    SQLModel.metadata.create_all(engine)
    print("Done! Tables recreated successfully.")