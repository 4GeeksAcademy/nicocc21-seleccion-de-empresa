#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.brasaland_api.incidents_database import seed_incident
from services.brasaland_api.incidents_seed_data import INCIDENTS_SEED


def run_incidents_seed(verbose: bool = True) -> tuple[int, int, int]:
    inserted = 0
    skipped = 0

    for payload in INCIDENTS_SEED:
        try:
            seed_incident(payload)
            inserted += 1
        except RuntimeError:
            skipped += 1

    total = len(INCIDENTS_SEED)

    if verbose:
        print("Seeder de incidencias completado")
        print(f"Total en seed: {total}")
        print(f"Insertados: {inserted}")
        print(f"Omitidos (ya existentes): {skipped}")

    return inserted, skipped, total


if __name__ == "__main__":
    run_incidents_seed(verbose=True)