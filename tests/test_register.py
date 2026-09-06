import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services.brasaland_api.models import UserCreate
from services.brasaland_api.routes.auth import register


def test_register_creates_user_without_exposing_password(test_database) -> None:
    result = register(UserCreate(email="new@example.com", password="secret123"))

    assert result.email == "new@example.com"
    assert not hasattr(result, "password_hash")


def test_register_rejects_duplicate_email(user: dict[str, object]) -> None:
    with pytest.raises(HTTPException) as error:
        register(UserCreate(email=str(user["email"]), password="another123"))

    assert error.value.detail == "Ya existe un usuario con ese email"


def test_register_rejects_empty_or_short_password() -> None:
    # La contraseña mínima es una regla de entrada del dominio, no de transporte HTTP.
    with pytest.raises(ValidationError):
        UserCreate(email="new@example.com", password="")