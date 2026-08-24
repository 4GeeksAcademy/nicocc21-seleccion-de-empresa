from __future__ import annotations

from pathlib import Path
from typing import Any

from tinydb import TinyDB
from tinydb.table import Document

from services.brasaland_api.incidents_models import (
    VALID_STATE_TRANSITIONS,
    utc_now,
)

DB_FILE = Path(__file__).resolve().parent / "data" / "incidents.json"
TABLE_NAME = "incidents"


def _open_db() -> TinyDB:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(DB_FILE, sort_keys=True, indent=2)


def _serialize(document: Document) -> dict[str, Any]:
    data = dict(document)
    data["id"] = int(document.doc_id)
    return data


def _next_sequence(table: Any) -> int:
    """Devuelve el siguiente número de secuencia para INC-XXXX."""
    all_docs = table.all()
    if not all_docs:
        return 1
    max_seq = 0
    for doc in all_docs:
        inc_id = doc.get("incident_id", "")
        if inc_id.startswith("INC-"):
            try:
                seq = int(inc_id.split("-")[1])
                if seq > max_seq:
                    max_seq = seq
            except (IndexError, ValueError):
                pass
    return max_seq + 1


def _matches(doc: dict[str, Any], field: str, value: str | None) -> bool:
    if value is None:
        return True
    return doc.get(field) == value


def _date_in_range(doc_date: str, desde: str | None, hasta: str | None) -> bool:
    if desde and doc_date < desde:
        return False
    if hasta and doc_date > hasta:
        return False
    return True


def list_incidents(
    estado: str | None = None,
    local_id: str | None = None,
    categoria: str | None = None,
    origen: str | None = None,
    prioridad: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
) -> list[dict[str, Any]]:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        docs = [_serialize(doc) for doc in table.all()]
    finally:
        db.close()

    filtered = [
        doc
        for doc in docs
        if _matches(doc, "estado", estado)
        and _matches(doc, "local_id", local_id)
        and _matches(doc, "categoria", categoria)
        and _matches(doc, "origen", origen)
        and _matches(doc, "prioridad", prioridad)
        and _date_in_range(doc.get("fecha_reporte", ""), desde, hasta)
    ]

    filtered.sort(key=lambda d: d.get("fecha_reporte", ""), reverse=True)
    return filtered


def get_incident(incident_id: int) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        doc = table.get(doc_id=incident_id)
        if doc is None:
            return None
        return _serialize(doc)
    finally:
        db.close()


def get_incident_by_incident_id(incident_id_str: str) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        results = table.search(
            lambda doc: doc.get("incident_id") == incident_id_str
        )
        if not results:
            return None
        return _serialize(results[0])
    finally:
        db.close()


def create_incident(payload: dict[str, Any]) -> dict[str, Any]:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        now = utc_now().isoformat()
        seq = _next_sequence(table)

        data: dict[str, Any] = {
            "incident_id": f"INC-{seq:04d}",
            "title": payload["title"],
            "description": payload["description"],
            "fecha_reporte": payload["fecha_reporte"],
            "local_id": payload["local_id"],
            "origen": payload["origen"],
            "categoria": payload["categoria"],
            "estado": "abierta",
            "prioridad": payload["prioridad"],
            "cliente_id": payload.get("cliente_id"),
            "cliente_email": payload.get("cliente_email"),
            "cliente_telefono": payload.get("cliente_telefono"),
            "satisfaccion": None,
            "created_at": now,
            "updated_at": now,
        }

        incident_id_num = int(table.insert(data))
        created = table.get(doc_id=incident_id_num)
        if created is None:
            raise RuntimeError("No se pudo recuperar la incidencia recien creada")
        return _serialize(created)
    finally:
        db.close()


def update_incident(incident_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        doc = table.get(doc_id=incident_id)
        if doc is None:
            return None

        now = utc_now().isoformat()
        safe_updates = {k: v for k, v in updates.items() if v is not None}
        safe_updates["updated_at"] = now

        table.update(safe_updates, doc_ids=[incident_id])
        updated = table.get(doc_id=incident_id)
        if updated is None:
            return None
        return _serialize(updated)
    finally:
        db.close()


def update_incident_status(incident_id: int, nuevo_estado: str) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        doc = table.get(doc_id=incident_id)
        if doc is None:
            return None

        estado_actual = doc.get("estado", "")
        transiciones_validas = VALID_STATE_TRANSITIONS.get(estado_actual, set())

        if nuevo_estado not in transiciones_validas:
            raise ValueError(
                f"No se puede cambiar estado de '{estado_actual}' a '{nuevo_estado}'. "
                f"Transiciones validas: {', '.join(sorted(transiciones_validas)) if transiciones_validas else 'ninguna'}"
            )

        now = utc_now().isoformat()
        table.update(
            {"estado": nuevo_estado, "updated_at": now},
            doc_ids=[incident_id],
        )

        updated = table.get(doc_id=incident_id)
        if updated is None:
            return None
        return _serialize(updated)
    finally:
        db.close()


def get_incidents_summary() -> dict[str, Any]:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        docs = [_serialize(doc) for doc in table.all()]
    finally:
        db.close()

    total = len(docs)
    by_state: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_origin: dict[str, int] = {}

    for doc in docs:
        estado = doc.get("estado", "desconocido")
        by_state[estado] = by_state.get(estado, 0) + 1

        categoria = doc.get("categoria", "desconocido")
        by_category[categoria] = by_category.get(categoria, 0) + 1

        prioridad = doc.get("prioridad", "desconocido")
        by_priority[prioridad] = by_priority.get(prioridad, 0) + 1

        origen = doc.get("origen", "desconocido")
        by_origin[origen] = by_origin.get(origen, 0) + 1

    return {
        "total": total,
        "by_state": dict(sorted(by_state.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "by_origin": dict(sorted(by_origin.items())),
    }


def seed_incident(payload: dict[str, Any]) -> dict[str, Any]:
    """Crea una incidencia desde el seed. Si ya existe (mismo incident_id), la omite."""
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        incident_id_str = payload.get("incident_id", "")

        existing = table.search(
            lambda doc: doc.get("incident_id") == incident_id_str
        )
        if existing:
            return _serialize(existing[0])

        now = utc_now().isoformat()
        data: dict[str, Any] = {
            **payload,
            "created_at": now,
            "updated_at": now,
        }

        incident_id_num = int(table.insert(data))
        created = table.get(doc_id=incident_id_num)
        if created is None:
            raise RuntimeError("No se pudo recuperar la incidencia seed recien creada")
        return _serialize(created)
    finally:
        db.close()