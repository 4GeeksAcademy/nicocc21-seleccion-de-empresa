from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tinydb import Query, TinyDB
from tinydb.table import Document

DB_FILE = Path(__file__).resolve().parent / "data" / "suppliers.json"
TABLE_NAME = "suppliers"


def _open_db() -> TinyDB:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(DB_FILE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(document: Document) -> dict[str, Any]:
    data = dict(document)
    data["id"] = int(document.doc_id)
    return data


def list_suppliers(country: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        docs = [_serialize(doc) for doc in table.all()]
    finally:
        db.close()

    if country:
        docs = [doc for doc in docs if doc.get("country") == country]
    if category:
        docs = [doc for doc in docs if category in doc.get("categories", [])]

    docs.sort(key=lambda item: (item.get("country", ""), item.get("name", "")))
    return docs


def get_supplier_by_id(supplier_id: int) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        doc = table.get(doc_id=supplier_id)
        if doc is None:
            return None
        return _serialize(doc)
    finally:
        db.close()


def create_supplier(payload: dict[str, Any]) -> dict[str, Any]:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        data = {
            **payload,
            "updated_at": utc_now().isoformat(),
        }
        supplier_id = int(table.insert(data))
        created = table.get(doc_id=supplier_id)
        if created is None:
            raise RuntimeError("No se pudo recuperar el proveedor recien creado")
        return _serialize(created)
    finally:
        db.close()


def update_supplier_rate(supplier_id: int, rate_per_unit: float) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        if table.get(doc_id=supplier_id) is None:
            return None

        table.update(
            {
                "rate_per_unit": rate_per_unit,
                "updated_at": utc_now().isoformat(),
            },
            doc_ids=[supplier_id],
        )

        updated = table.get(doc_id=supplier_id)
        if updated is None:
            return None
        return _serialize(updated)
    finally:
        db.close()


def update_supplier_status(supplier_id: int, status: str) -> dict[str, Any] | None:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        if table.get(doc_id=supplier_id) is None:
            return None

        table.update({"status": status}, doc_ids=[supplier_id])

        updated = table.get(doc_id=supplier_id)
        if updated is None:
            return None
        return _serialize(updated)
    finally:
        db.close()


def delete_supplier(supplier_id: int) -> bool:
    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        if table.get(doc_id=supplier_id) is None:
            return False
        table.remove(doc_ids=[supplier_id])
        return True
    finally:
        db.close()


def seed_suppliers(seed_data: list[dict[str, Any]]) -> tuple[int, int]:
    db = _open_db()
    inserted = 0
    skipped = 0

    try:
        table = db.table(TABLE_NAME)
        supplier_query = Query()

        for item in seed_data:
            exists = table.contains(
                (supplier_query.name == item["name"])
                & (supplier_query.country == item["country"])
            )
            if exists:
                skipped += 1
                continue

            table.insert(
                {
                    **item,
                    "updated_at": utc_now().isoformat(),
                }
            )
            inserted += 1

        return inserted, skipped
    finally:
        db.close()
