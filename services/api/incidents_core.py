from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "incident_id",
    "fecha_reporte",
    "local_id",
    "cliente_id",
    "cliente_email",
    "cliente_telefono",
    "categoria",
    "estado",
    "prioridad",
    "descripcion",
]

VALID_LOCAL_IDS = {f"L{i:02d}" for i in range(1, 15)}
VALID_CATEGORIES = {"queja", "solicitud", "fallo_operativo"}
VALID_STATES = {"abierto", "cerrado", "descartado"}
VALID_PRIORITIES = {"baja", "media", "alta", "critica"}


class IncidentsValidationError(Exception):
    pass


def _validate_headers(headers: list[str]) -> None:
    if not headers:
        raise IncidentsValidationError("El archivo CSV no tiene cabecera")

    missing_headers = [field for field in REQUIRED_FIELDS if field not in headers]
    if missing_headers:
        missing = ", ".join(missing_headers)
        raise IncidentsValidationError(
            f"Faltan columnas obligatorias en la cabecera: {missing}"
        )


def load_rows_from_path(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists() or not csv_path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {csv_path}")
    if csv_path.stat().st_size == 0:
        raise IncidentsValidationError("El archivo CSV esta vacio")

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames or []
        _validate_headers(headers)
        return list(reader)


def load_rows_from_text(csv_text: str) -> list[dict[str, str]]:
    if not csv_text.strip():
        raise IncidentsValidationError("El archivo CSV esta vacio")

    reader = csv.DictReader(io.StringIO(csv_text))
    headers = reader.fieldnames or []
    _validate_headers(headers)
    return list(reader)


def validate_row(row: dict[str, str]) -> str | None:
    for field in REQUIRED_FIELDS:
        if not (row.get(field) or "").strip():
            return "campo_faltante"

    local_id = (row.get("local_id") or "").strip()
    if local_id not in VALID_LOCAL_IDS:
        return "local_id_fuera_de_rango"

    categoria = (row.get("categoria") or "").strip()
    if categoria not in VALID_CATEGORIES:
        return "categoria_fuera_de_rango"

    estado = (row.get("estado") or "").strip()
    if estado not in VALID_STATES:
        return "estado_fuera_de_rango"

    prioridad = (row.get("prioridad") or "").strip()
    if prioridad not in VALID_PRIORITIES:
        return "prioridad_fuera_de_rango"

    satisfaccion_raw = (row.get("satisfaccion") or "").strip()
    if satisfaccion_raw:
        try:
            satisfaccion = int(satisfaccion_raw)
        except ValueError:
            return "satisfaccion_no_numerica"
        if satisfaccion < 1 or satisfaccion > 5:
            return "satisfaccion_fuera_de_rango"

    return None


def analyze_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    invalid_reasons: Counter[str] = Counter()
    category_totals: Counter[str] = Counter()
    state_totals: Counter[str] = Counter()

    valid_rows = 0
    invalid_rows = 0
    closed_scores: list[int] = []

    for row in rows:
        reason = validate_row(row)
        if reason is not None:
            invalid_rows += 1
            invalid_reasons[reason] += 1
            continue

        valid_rows += 1
        categoria = (row.get("categoria") or "").strip()
        estado = (row.get("estado") or "").strip()

        category_totals[categoria] += 1
        state_totals[estado] += 1

        satisfaccion_raw = (row.get("satisfaccion") or "").strip()
        if estado == "cerrado" and satisfaccion_raw:
            closed_scores.append(int(satisfaccion_raw))

    avg_satisfaction = (
        round(sum(closed_scores) / len(closed_scores), 4) if closed_scores else 0.0
    )

    return {
        "total_processed": len(rows),
        "total_valid": valid_rows,
        "total_invalid": invalid_rows,
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "by_category": dict(sorted(category_totals.items())),
        "by_state": dict(sorted(state_totals.items())),
        "closed_with_score": len(closed_scores),
        "avg_satisfaction_closed_with_score": avg_satisfaction,
    }


def summary_to_csv_text(summary: dict[str, Any]) -> str:
    rows: list[tuple[str, str]] = [
        ("total_procesados", str(summary["total_processed"])),
        ("total_validos", str(summary["total_valid"])),
        ("total_invalidos", str(summary["total_invalid"])),
    ]

    for reason, count in summary["invalid_reasons"].items():
        rows.append((f"invalidos_{reason}", str(count)))

    for category, count in summary["by_category"].items():
        rows.append((f"categoria_{category}", str(count)))

    for state, count in summary["by_state"].items():
        rows.append((f"estado_{state}", str(count)))

    rows.append(("cerrados_con_satisfaccion", str(summary["closed_with_score"])))
    rows.append(
        (
            "indice_satisfaccion_medio",
            str(summary["avg_satisfaction_closed_with_score"]),
        )
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metrica", "valor"])
    writer.writerows(rows)
    return output.getvalue()
