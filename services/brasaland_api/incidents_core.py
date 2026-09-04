"""
incidents_core — Analisis y validacion de incidencias CSV (legacy).

ADVERTENCIA: Este modulo es un wrapper de compatibilidad hacia atras.
Toda la logica de validacion se ha movido a packages/shared/validators/incidents.py.

Los consumidores existentes (app.py, analyze.py) siguen funcionando
importando desde aqui sin cambios.
"""

from packages.shared.validators.incidents import (
    REQUIRED_FIELDS,
    VALID_CATEGORIES,
    VALID_LOCAL_IDS,
    VALID_PRIORITIES,
    VALID_STATES,
    IncidentsValidationError,
    _validate_headers,
    analyze_rows,
    load_rows_from_path,
    load_rows_from_text,
    summary_to_csv_text,
    validate_row,
)

__all__ = [
    "REQUIRED_FIELDS",
    "VALID_CATEGORIES",
    "VALID_LOCAL_IDS",
    "VALID_PRIORITIES",
    "VALID_STATES",
    "IncidentsValidationError",
    "_validate_headers",
    "analyze_rows",
    "load_rows_from_path",
    "load_rows_from_text",
    "summary_to_csv_text",
    "validate_row",
]