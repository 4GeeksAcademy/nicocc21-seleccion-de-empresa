#!/usr/bin/env python3
"""Seed de incidencias desde CSV historico al nuevo sistema.

Uso:
    python3 scripts/seed_incidents.py scripts/incidents-BRASALAND.csv

Convierte el formato CSV legacy (abierto/cerrado/descartado) al nuevo
modelo (abierta/en_progreso/resuelta/descartada) y llama a seed_incident()
para cada fila valida.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from packages.shared.validators.incidents import (
    IncidentsValidationError,
    load_rows_from_path,
    validate_row,
)
from services.brasaland_api.incidents_database import seed_incident

# Mapa de estados legacy -> nuevo modelo
LEGACY_TO_NEW_STATE = {
    "abierto": "abierta",
    "cerrado": "resuelta",
    "descartado": "descartada",
}

DEFAULT_ORIGEN = "interno"

# Columnas CSV legacy que se esperan
CSV_TO_MODEL_FIELDS = {
    "incident_id": "incident_id",
    "fecha_reporte": "fecha_reporte",
    "local_id": "local_id",
    "cliente_id": "cliente_id",
    "cliente_email": "cliente_email",
    "cliente_telefono": "cliente_telefono",
    "categoria": "categoria",
    "prioridad": "prioridad",
    "descripcion": "description",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed de incidencias desde CSV historico."
    )
    parser.add_argument("csv_path", help="Ruta al archivo CSV de incidencias")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar lo que se importaria sin escribir en BD",
    )
    parser.add_argument(
        "--origen",
        default=DEFAULT_ORIGEN,
        choices=["cliente", "interno"],
        help="Origen por defecto para las incidencias (default: interno)",
    )
    return parser.parse_args()


def row_to_seed_payload(row: dict[str, str], default_origen: str) -> dict:
    """Convierte una fila CSV legacy al payload para seed_incident()."""
    payload: dict = {}

    for csv_field, model_field in CSV_TO_MODEL_FIELDS.items():
        value = (row.get(csv_field) or "").strip()
        if model_field == "description":
            payload["description"] = value
        else:
            payload[model_field] = value

    # Generar title a partir de la descripcion
    desc = (row.get("descripcion") or "").strip()
    payload["title"] = desc[:100] if len(desc) > 100 else desc

    # Mapear estado legacy -> nuevo modelo
    estado_legacy = (row.get("estado") or "").strip().lower()
    payload["estado"] = LEGACY_TO_NEW_STATE.get(estado_legacy, "abierta")

    # Origen
    payload["origen"] = default_origen

    # Satisfaccion (opcional)
    satisfaccion_raw = (row.get("satisfaccion") or "").strip()
    if satisfaccion_raw:
        try:
            payload["satisfaccion"] = int(satisfaccion_raw)
        except ValueError:
            payload["satisfaccion"] = None
    else:
        payload["satisfaccion"] = None

    return payload


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv_path)

    try:
        rows = load_rows_from_path(csv_path)
    except (FileNotFoundError, IncidentsValidationError) as error:
        print(f"Error al leer CSV: {error}")
        return 1

    total = len(rows)
    validos = 0
    invalidos = 0
    insertados = 0
    omitidos = 0
    errores = 0

    print(f"Procesando {total} fila(s) desde: {csv_path}")
    print(f"Origen por defecto: {args.origen}")
    if args.dry_run:
        print("[DRY RUN] No se escribiran datos en la base de datos")
    print("-" * 60)

    for i, row in enumerate(rows, start=1):
        reason = validate_row(row)
        if reason is not None:
            print(f"  [{i:04d}] INVALIDA ({reason}): {row.get('incident_id', '?')}")
            invalidos += 1
            continue

        validos += 1
        payload = row_to_seed_payload(row, args.origen)

        if args.dry_run:
            print(f"  [{i:04d}] OK: {payload.get('incident_id')} -> {payload.get('estado')}")
            insertados += 1
            continue

        try:
            result = seed_incident(payload)
            if result.get("created_at") == result.get("updated_at"):
                # Recien creado (created_at == updated_at significa primera vez)
                print(f"  [{i:04d}] INSERTADO: {result.get('incident_id')}")
                insertados += 1
            else:
                print(f"  [{i:04d}] OMITIDO (ya existe): {result.get('incident_id')}")
                omitidos += 1
        except Exception as e:
            print(f"  [{i:04d}] ERROR: {e}")
            errores += 1

    print("-" * 60)
    print(f"Resumen: {total} procesadas, {validos} validas, {invalidos} invalidas")
    if args.dry_run:
        print(f"         {insertados} se insertarian (dry-run)")
    else:
        print(f"         {insertados} insertadas, {omitidos} omitidas, {errores} errores")

    return 0 if errores == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())