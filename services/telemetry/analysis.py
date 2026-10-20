"""Métricas de telemetría con Pandas — Fase 1.

Cada función es **independiente y sin efectos secundarios**:
dos llamadas con los mismos parámetros devuelven el mismo resultado.

Todas las métricas son **técnicas/operacionales** (volumen, errores, latencia),
ninguna es de negocio (ventas, conversión, ingresos).

Las funciones **no aplican su propia ventana por defecto**:
el endpoint resuelve el período una sola vez y lo pasa a cada función.

Convención interna (orden de operaciones):
  1. Cargar datos desde Supabase (SQLModel/SQLAlchemy)
  2. Convertir a DataFrame de Pandas
  3. Refinar tipos (timestamp → datetime con utc=True)
  4. Agrupar y agregar (sin loops)
  5. Retornar lista de dicts serializable a JSON
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlmodel import Session, text

from services.brasaland_api.database import engine

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Métrica 1 — Volumen diario de eventos
# ──────────────────────────────────────────────

def events_per_day(
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Volumen diario de eventos agrupado por día y tipo de evento.

    Responde: ¿cuántos eventos de cada tipo se registran por día?

    Args:
        start_date: Inicio del período (UTC, obligatorio).
        end_date: Fin del período (UTC, obligatorio).

    Returns:
        Lista de dictos con las claves ``date``, ``event_type`` y ``count``.
    """
    df = _load_events(start_date, end_date)
    if df.empty:
        return []

    # Timestamps ya convertidos en _load_events; agrupamos por fecha y tipo
    df["date"] = df["timestamp"].dt.date
    grouped = df.groupby(["date", "event_type"]).agg(count=("event_id", "count")).reset_index()
    grouped["date"] = grouped["date"].astype(str)
    return grouped.to_dict(orient="records")


# ──────────────────────────────────────────────
# Métrica 2 — Tasa de error por tipo de evento
# ──────────────────────────────────────────────

def error_rate_by_type(
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Tasa de eventos con error (status_code >= 400 o validation_failed)
    agrupada por tipo de evento.

    Responde: ¿qué tipo de evento presenta mayor proporción de errores?

    Para eventos ``api_request_completed`` se considera error si
    ``status_code >= 400`` en properties.
    Los eventos ``validation_failed`` se cuentan como error al 100%.

    Args:
        start_date: Inicio del período (UTC, obligatorio).
        end_date: Fin del período (UTC, obligatorio).

    Returns:
        Lista de dictos con las claves ``event_type``, ``total``,
        ``errors`` y ``error_rate`` (float entre 0 y 1).
    """
    df = _load_events(start_date, end_date)
    if df.empty:
        return []

    # Extraer status_code de properties para api_request_completed
    df["status_code"] = df.apply(
        lambda row: (
            row["properties"].get("status_code")
            if isinstance(row["properties"], dict) and row["event_type"] == "api_request_completed"
            else None
        ),
        axis=1,
    )

    # Marcar como error: validation_failed siempre es error,
    # api_request_completed con status_code >= 400 es error
    df["is_error"] = (
        (df["event_type"] == "validation_failed")
        | (
            (df["event_type"] == "api_request_completed")
            & df["status_code"].notna()
            & (df["status_code"] >= 400)
        )
    )

    grouped = df.groupby("event_type").agg(
        total=("event_id", "count"),
        errors=("is_error", "sum"),
    ).reset_index()

    grouped["error_rate"] = (grouped["errors"] / grouped["total"]).round(4)
    return grouped.to_dict(orient="records")


# ──────────────────────────────────────────────
# Métrica 3 — Latencia de API (percentiles)
# ──────────────────────────────────────────────

def api_latency_summary(
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Percentiles de latencia (duration_ms) de ``api_request_completed``
    agrupados por ruta (route_template) y método HTTP.

    Responde: ¿qué rutas son más lentas y cuál es su percentil 50/90/99?

    Args:
        start_date: Inicio del período (UTC, obligatorio).
        end_date: Fin del período (UTC, obligatorio).

    Returns:
        Lista de dictos con las claves ``route_template``, ``method``,
        ``count``, ``p50_ms``, ``p90_ms``, ``p99_ms`` y ``mean_ms``.
    """
    df = _load_events(start_date, end_date)
    if df.empty:
        return []

    # Filtrar solo api_request_completed con duration_ms
    df = df[df["event_type"] == "api_request_completed"].copy()
    if df.empty:
        return []

    df["duration_ms"] = df.apply(
        lambda row: (
            row["properties"].get("duration_ms")
            if isinstance(row["properties"], dict)
            else None
        ),
        axis=1,
    )
    df = df.dropna(subset=["duration_ms"]).copy()
    if df.empty:
        return []

    df["route_template"] = df.apply(
        lambda row: (
            row["properties"].get("route_template", "/unknown")
            if isinstance(row["properties"], dict)
            else "/unknown"
        ),
        axis=1,
    )
    df["method"] = df.apply(
        lambda row: (
            row["properties"].get("method", "UNKNOWN")
            if isinstance(row["properties"], dict)
            else "UNKNOWN"
        ),
        axis=1,
    )

    grouped = df.groupby(["route_template", "method"]).agg(
        count=("duration_ms", "count"),
        p50_ms=("duration_ms", lambda x: x.quantile(0.50)),
        p90_ms=("duration_ms", lambda x: x.quantile(0.90)),
        p99_ms=("duration_ms", lambda x: x.quantile(0.99)),
        mean_ms=("duration_ms", "mean"),
    ).reset_index()

    for col in ("p50_ms", "p90_ms", "p99_ms", "mean_ms"):
        grouped[col] = grouped[col].round(1)

    return grouped.to_dict(orient="records")


# ──────────────────────────────────────────────
# Métrica adicional — Tasa diaria de fallos de autenticación
# ──────────────────────────────────────────────

def auth_failure_rate(
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Tasa diaria de fallos de login.

    Fórmula: ``user_login_failed / (user_login_failed + user_login_succeeded)``
    por día. Si no hubo intentos en un día, se omite (división por cero).

    Responde: ¿qué días la autenticación tuvo mayor tasa de fallo?

    Args:
        start_date: Inicio del período (UTC, obligatorio).
        end_date: Fin del período (UTC, obligatorio).

    Returns:
        Lista de dictos con las claves ``date``, ``attempts``,
        ``failures``, ``successes`` y ``failure_rate`` (float entre 0 y 1).
    """
    df = _load_events(start_date, end_date)
    if df.empty:
        return []

    # Filtrar solo eventos de login
    login_types = {"login_succeeded", "login_failed"}
    df = df[df["event_type"].isin(login_types)].copy()
    if df.empty:
        return []

    df["date"] = df["timestamp"].dt.date
    grouped = df.groupby(["date", "event_type"]).agg(count=("event_id", "count")).reset_index()

    # Pivot: una fila por día con columnas login_succeeded, login_failed
    pivot = grouped.pivot_table(
        index="date",
        columns="event_type",
        values="count",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    # Asegurar que ambas columnas existan
    for col in login_types:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["attempts"] = pivot["login_succeeded"] + pivot["login_failed"]
    pivot["failures"] = pivot["login_failed"]
    pivot["successes"] = pivot["login_succeeded"]
    pivot["failure_rate"] = (
        pivot["failures"] / pivot["attempts"]
    ).round(4)

    # Reemplazar NaN (0/0) con None — no hubo intentos ese día
    pivot["failure_rate"] = pivot["failure_rate"].where(pivot["attempts"] > 0, None)

    result = pivot[["date", "attempts", "failures", "successes", "failure_rate"]].copy()
    result["date"] = result["date"].astype(str)
    return result.to_dict(orient="records")


# ──────────────────────────────────────────────
# Carga común desde Supabase
# ──────────────────────────────────────────────

def _load_events(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Carga eventos de telemetría en el rango [start_date, end_date) y
    devuelve un DataFrame de Pandas con tipos ya convertidos.

    Sin eventos en el rango, devuelve un DataFrame vacío.
    """
    query = text("""
        SELECT
            event_id,
            timestamp,
            event_type,
            properties,
            request_id,
            session_id,
            user_id,
            schema_version,
            received_at
        FROM telemetry_events
        WHERE timestamp >= :start_date AND timestamp < :end_date
        ORDER BY timestamp ASC
    """)

    with Session(engine) as session:
        rows = session.execute(
            query,
            {"start_date": start_date, "end_date": end_date},
        ).mappings().all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(row) for row in rows])

    # Convertir timestamps a datetime con utc=True
    for col in ("timestamp", "received_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)

    return df