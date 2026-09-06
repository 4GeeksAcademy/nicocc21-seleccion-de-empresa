from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.brasaland_api import auth
from services.brasaland_api.routes.auth import login


def test_login_returns_bearer_token(user: dict[str, object]) -> None:
    result = login(SimpleNamespace(username=user["email"], password="secret123"))

    assert result.token_type == "bearer"
    assert auth.decode_token(result.access_token) == user["id"]


def test_login_rejects_wrong_credentials() -> None:
    with pytest.raises(HTTPException) as error:
        login(SimpleNamespace(username="missing@example.com", password="wrong"))

    assert error.value.detail == "Email o contraseña incorrectos"


def test_login_rejects_empty_password(user: dict[str, object]) -> None:
    with pytest.raises(HTTPException) as error:
        login(SimpleNamespace(username=user["email"], password=""))

    assert error.value.detail == "Email o contraseña incorrectos"