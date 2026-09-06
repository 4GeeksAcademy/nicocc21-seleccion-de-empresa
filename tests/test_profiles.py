from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.brasaland_api.models import ProfileCreate, ProfileUpdate
from services.brasaland_api.routes import profiles


CURRENT_USER = {"id": 7, "email": "user@example.com"}


def test_create_profile_returns_the_created_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = {
        "id": 1,
        "user_id": 7,
        "full_name": "Ana Torres",
        "phone": "3001234567",
        "address": "Calle 10",
    }
    monkeypatch.setattr(profiles, "create_profile", lambda user_id, data: profile)

    result = profiles.create_my_profile(
        ProfileCreate(full_name="Ana Torres", phone="3001234567", address="Calle 10"),
        CURRENT_USER,
    )

    assert result.id == 1
    assert result.user_id == 7
    assert result.full_name == "Ana Torres"


def test_create_profile_rejects_a_duplicate_profile() -> None:
    def duplicate_profile(user_id: int, data: dict[str, object]) -> dict[str, object]:
        raise ValueError("profile already exists")

    original = profiles.create_profile
    profiles.create_profile = duplicate_profile
    try:
        with pytest.raises(HTTPException) as error:
            profiles.create_my_profile(ProfileCreate(full_name="Ana Torres"), CURRENT_USER)
    finally:
        profiles.create_profile = original

    assert error.value.detail == "El usuario ya tiene un perfil"


def test_get_profile_returns_not_found_when_user_has_no_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profiles, "get_profile_by_user_id", lambda user_id: None)

    with pytest.raises(HTTPException) as error:
        profiles.get_my_profile(CURRENT_USER)

    assert error.value.detail == "Perfil no encontrado"


def test_update_profile_returns_updated_business_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updated_profile = {
        "id": 1,
        "user_id": 7,
        "full_name": "Ana Torres Gómez",
        "phone": None,
        "address": "Carrera 20",
    }
    monkeypatch.setattr(profiles, "update_profile", lambda user_id, data: updated_profile)

    result = profiles.update_my_profile(
        ProfileUpdate(full_name="Ana Torres Gómez", address="Carrera 20"),
        CURRENT_USER,
    )

    assert result.full_name == "Ana Torres Gómez"
    assert result.address == "Carrera 20"


def test_put_profile_returns_not_found_when_profile_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profiles, "get_profile_by_user_id", lambda user_id: None)

    with pytest.raises(HTTPException) as error:
        profiles.put_my_profile(ProfileUpdate(full_name="Ana Torres"), CURRENT_USER)

    assert error.value.detail == "Perfil no encontrado"
