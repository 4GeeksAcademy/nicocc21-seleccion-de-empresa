from __future__ import annotations

import argparse

from sqlalchemy import Engine, inspect
from sqlalchemy.schema import CreateColumn, CreateIndex, CreateTable

from services.brasaland_api.inventory_models import IngredientEntry, IngredientExit, IngredientLocation


def migrate_inventory_telemetry(engine: Engine, apply: bool = False) -> list[str]:
    inspector = inspect(engine)
    statements: list[str] = []
    additions = {
        IngredientEntry: ("supplier_id", "unit_price", "currency"),
        IngredientExit: ("waste_reason",),
    }
    for model, names in additions.items():
        table = model.__table__
        if not inspector.has_table(table.name):
            raise RuntimeError("Crear el inventario inicial antes de migrar")
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for name in names:
            if name not in existing:
                column = CreateColumn(table.c[name]).compile(dialect=engine.dialect)
                statements.append(f'ALTER TABLE "{table.name}" ADD COLUMN {column}')
    table = IngredientLocation.__table__
    if not inspector.has_table(table.name):
        statements.append(str(CreateTable(table).compile(dialect=engine.dialect)))
    existing_indexes = {index["name"] for index in inspector.get_indexes(IngredientEntry.__tablename__)}
    for index in IngredientEntry.__table__.indexes:
        if "supplier_id" in index.columns and index.name not in existing_indexes:
            statements.append(str(CreateIndex(index).compile(dialect=engine.dialect)))
    if apply and statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
    return statements


if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"))
    from services.brasaland_api.database import engine

    parser = argparse.ArgumentParser(description="Migracion aditiva de inventario; sin --apply solo muestra SQL")
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    plan = migrate_inventory_telemetry(engine, apply=arguments.apply)
    print("\n".join(plan) if plan else "Sin cambios pendientes")