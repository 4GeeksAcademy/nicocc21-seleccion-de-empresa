from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.brasaland_api.models import MessageResponse, UserCreate, UserRegisteredOut
from services.brasaland_api.routes import users


def test_create_user_endpoint_registers_without_exposing_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = {
        "id": 7,
        "email": "nuevo@example.com",
        "password_hash": "hash-interno",
        "is_active": True,
        "role": "user",
        "created_at": "2026-10-13T00:00:00+00:00",
    }
    monkeypatch.setattr(users, "create_user", lambda email, password_hash: created)
    monkeypatch.setattr(users, "hash_password", lambda password: "hash-interno")

    result = users.create_user_endpoint(
        UserCreate(email="nuevo@example.com", password="secret123")
    )

    # El flujo público de registro no reenvía el email (criterio de auth de la academia).
    assert isinstance(result, UserRegisteredOut)
    assert result.id == 7
    assert result.role == "user"
    assert not hasattr(result, "email")
    assert not hasattr(result, "password_hash")


def test_create_user_endpoint_returns_conflict_on_duplicate_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def duplicate(email: str, password_hash: str) -> dict[str, object]:
        raise ValueError("Ya existe un usuario con ese email")

    monkeypatch.setattr(users, "create_user", duplicate)

    with pytest.raises(HTTPException) as error:
        users.create_user_endpoint(UserCreate(email="dup@example.com", password="secret123"))

    assert error.value.status_code == 409
    assert error.value.detail == "Ya existe un usuario con ese email"


def test_delete_user_endpoint_returns_message_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = {"id": 1, "email": "admin@brasaland.test", "role": "admin"}
    monkeypatch.setattr(users, "delete_user", lambda user_id: True)

    result = users.delete_user_endpoint(3, admin)

    assert isinstance(result, MessageResponse)
    assert result.message == "Usuario eliminado"


def test_delete_user_endpoint_forbids_non_owner() -> None:
    normal_user = {"id": 1, "email": "user@brasaland.test", "role": "user"}

    with pytest.raises(HTTPException) as error:
        users.delete_user_endpoint(99, normal_user)

    assert error.value.status_code == 403