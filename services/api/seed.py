#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api.database import seed_suppliers
from services.api.suppliers_seed_data import SUPPLIERS_SEED


def run_seed(verbose: bool = True) -> tuple[int, int, int]:
    inserted, skipped = seed_suppliers(SUPPLIERS_SEED)
    total = len(SUPPLIERS_SEED)

    if verbose:
        print("Seeder de proveedores completado")
        print(f"Total en seed: {total}")
        print(f"Insertados: {inserted}")
        print(f"Omitidos (ya existentes): {skipped}")

    return inserted, skipped, total


if __name__ == "__main__":
    run_seed(verbose=True)
