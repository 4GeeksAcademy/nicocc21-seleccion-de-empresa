"""Exportador CSV de telemetría para el script nocturno (DEV-53).

Exporta ``telemetry_events`` del día ``target_date`` (UTC) a
``data/raw/telemetry_YYYY-MM-DD.csv`` con publicación atómica.

El CSV incluye todas las columnas del modelo ``TelemetryEventRecord``
excepto ``id`` (serial interno). ``properties`` se exporta como JSON.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session

from services.brasaland_api.database import engine

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# Columnas del CSV en el orden de exportación
CSV_COLUMNS = [
    "event_id",
    "timestamp",
    "event_type",
    "schema_version",
    "request_id",
    "session_id",
    "user_id",
    "properties",
    "received_at",
]


def export_telemetry_csv(target_date: str) -> Path:
    """Exporta eventos de ``target_date`` a un CSV y retorna la ruta absoluta.

    Args:
        target_date: Fecha ISO ``YYYY-MM-DD`` en UTC.

    Returns:
        Ruta absoluta al archivo CSV generado.

    Raises:
        RuntimeError: si falla la escritura atómica del archivo.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = RAW_DIR / f"telemetry_{target_date}.csv"
    if dest_path.exists():
        return dest_path.resolve()

    start_dt = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    query = text("""
        SELECT
            event_id,
            timestamp,
            event_type,
            schema_version,
            request_id,
            session_id,
            user_id,
            properties,
            received_at
        FROM telemetry_events
        WHERE timestamp >= :start_date AND timestamp < :end_date
        ORDER BY timestamp ASC
    """)

    with Session(engine) as session:
        rows = session.execute(
            query,
            {"start_date": start_dt, "end_date": end_dt},
        ).mappings().all()

    # Publicación atómica: escribir a temporal y renombrar
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".csv", prefix=f"telemetry_{target_date}_", dir=str(RAW_DIR)
    )
    try:
        with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                row_dict = dict(row)
                # serializar properties como JSON string
                if isinstance(row_dict.get("properties"), dict):
                    row_dict["properties"] = json.dumps(row_dict["properties"], ensure_ascii=False)
                if isinstance(row_dict.get("timestamp"), datetime):
                    row_dict["timestamp"] = row_dict["timestamp"].isoformat()
                if isinstance(row_dict.get("received_at"), datetime):
                    row_dict["received_at"] = row_dict["received_at"].isoformat()
                writer.writerow(row_dict)

        # Renombrar atómicamente
        shutil.move(tmp_path, dest_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return dest_path.resolve()