from __future__ import annotations

import hashlib
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


# =============================================================================
# Users
# =============================================================================

USERS_TABLE = "users"


def create_user(
    email: str,
    password_hash: str,
    role: str = "user",
) -> dict[str, Any]:
    """Crea un usuario con credenciales. Retorna el usuario creado."""
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        if table.contains(Query().email == email):
            raise ValueError("Ya existe un usuario con ese email")
        user_id = int(table.insert({
            "email": email,
            "password_hash": password_hash,
            "is_active": True,
            "role": role,
            "created_at": utc_now().isoformat(),
        }))
        return _serialize(table.get(doc_id=user_id))
    finally:
        db.close()


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Busca usuario por email (para login)."""
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        doc = table.get(Query().email == email)
        return _serialize(doc) if doc else None
    finally:
        db.close()


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Busca usuario por ID."""
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        doc = table.get(doc_id=user_id)
        return _serialize(doc) if doc else None
    finally:
        db.close()


def list_users() -> list[dict[str, Any]]:
    """Lista todos los usuarios."""
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        return [_serialize(doc) for doc in table.all()]
    finally:
        db.close()


def update_user(user_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Actualiza campos de credenciales de un usuario (email, role, is_active)."""
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        doc = table.get(doc_id=user_id)
        if doc is None:
            return None
        # Verificar que el email no esté en uso por otro usuario
        if "email" in data and data["email"] != doc.get("email"):
            if table.contains(Query().email == data["email"]):
                raise ValueError("Ya existe otro usuario con ese email")
        updates = {k: v for k, v in data.items() if v is not None}
        if not updates:
            return _serialize(doc)
        table.update(updates, doc_ids=[user_id])
        return _serialize(table.get(doc_id=user_id))
    finally:
        db.close()


def delete_user(user_id: int) -> bool:
    """Elimina un usuario y su perfil asociado. Retorna True si existía."""
    db = _open_db()
    try:
        users = db.table(USERS_TABLE)
        profiles = db.table(PROFILES_TABLE)
        if users.get(doc_id=user_id) is None:
            return False
        users.remove(doc_ids=[user_id])
        profile = profiles.get(Query().user_id == user_id)
        if profile:
            profiles.remove(doc_ids=[profile.doc_id])
        return True
    finally:
        db.close()


# =============================================================================
# Profiles
# =============================================================================

PROFILES_TABLE = "profiles"


def create_profile(user_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Crea un perfil vinculado a un usuario."""
    db = _open_db()
    try:
        profiles = db.table(PROFILES_TABLE)
        if profiles.contains(Query().user_id == user_id):
            raise ValueError("El usuario ya tiene un perfil")
        profile_id = int(profiles.insert({"user_id": user_id, **data}))
        return _serialize(profiles.get(doc_id=profile_id))
    finally:
        db.close()


def get_profile_by_user_id(user_id: int) -> dict[str, Any] | None:
    """Busca perfil por user_id."""
    db = _open_db()
    try:
        profiles = db.table(PROFILES_TABLE)
        doc = profiles.get(Query().user_id == user_id)
        return _serialize(doc) if doc else None
    finally:
        db.close()


def update_profile(user_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Actualiza perfil existente. Solo actualiza campos no None."""
    db = _open_db()
    try:
        profiles = db.table(PROFILES_TABLE)
        doc = profiles.get(Query().user_id == user_id)
        if doc is None:
            return None
        updates = {k: v for k, v in data.items() if v is not None}
        if not updates:
            return _serialize(doc)
        profiles.update(updates, doc_ids=[doc.doc_id])
        return _serialize(profiles.get(doc_id=doc.doc_id))
    finally:
        db.close()


# =============================================================================
# AUTH-03: Password Reset
# =============================================================================

RESET_TOKENS_TABLE = "password_resets"


def hash_token(token: str) -> str:
    """Hashea un token con SHA-256 para almacenamiento seguro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def update_user_password(user_id: int, new_password_hash: str) -> bool:
    """Actualiza la contraseña de un usuario y marca password_changed_at.

    Retorna True si se actualizó correctamente.
    """
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        doc = table.get(doc_id=user_id)
        if doc is None:
            return False
        table.update(
            {
                "password_hash": new_password_hash,
                "password_changed_at": utc_now().isoformat(),
            },
            doc_ids=[user_id],
        )
        return True
    finally:
        db.close()


def store_reset_token(user_id: int, token_hash: str, expires_at: str) -> None:
    """Almacena un token de restablecimiento en la tabla password_resets."""
    db = _open_db()
    try:
        tokens = db.table(RESET_TOKENS_TABLE)
        tokens.insert({
            "user_id": user_id,
            "token_hash": token_hash,
            "used": False,
            "expires_at": expires_at,
            "created_at": utc_now().isoformat(),
        })
    finally:
        db.close()


def get_reset_token_record(token_hash: str) -> dict[str, Any] | None:
    """Busca un registro de token por su hash."""
    db = _open_db()
    try:
        tokens = db.table(RESET_TOKENS_TABLE)
        doc = tokens.get(Query().token_hash == token_hash)
        return _serialize(doc) if doc else None
    finally:
        db.close()


def mark_reset_token_used(token_hash: str) -> bool:
    """Marca un token como usado. Retorna True si existía."""
    db = _open_db()
    try:
        tokens = db.table(RESET_TOKENS_TABLE)
        doc = tokens.get(Query().token_hash == token_hash)
        if doc is None:
            return False
        tokens.update({"used": True}, doc_ids=[doc.doc_id])
        return True
    finally:
        db.close()


def is_token_used_or_expired(token_hash: str, now_iso: str) -> bool:
    """Verifica si un token ya fue usado o expiró.

    Retorna True si el token no existe, ya fue usado, o su expires_at
    es anterior a now_iso.
    """
    record = get_reset_token_record(token_hash)
    if record is None:
        return True
    if record.get("used", False):
        return True
    expires_at = record.get("expires_at", "")
    if expires_at < now_iso:
        return True
    return False


def get_user_password_changed_at(user_id: int) -> str | None:
    """Obtiene la fecha del último cambio de contraseña.

    Se usa para invalidar tokens emitidos antes de ese momento.
    """
    db = _open_db()
    try:
        table = db.table(USERS_TABLE)
        doc = table.get(doc_id=user_id)
        return doc.get("password_changed_at") if doc else None
    finally:
        db.close()
