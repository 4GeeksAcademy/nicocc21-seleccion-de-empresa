from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from services.brasaland_api import auth


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password_hash = auth.hash_password("secret123")

    assert password_hash != "secret123"
    assert auth.verify_password("secret123", password_hash)
    assert not auth.verify_password("wrong", password_hash)


def test_access_token_contains_user_and_expiration() -> None:
    token = auth.create_access_token(42)
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])

    assert payload["sub"] == "42"
    assert "exp" in payload
    assert auth.decode_token(token) == 42


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: jwt.encode(
            {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            auth.SECRET_KEY,
            algorithm=auth.ALGORITHM,
        ),
        lambda: "not-a-jwt",
    ],
)
def test_decode_token_rejects_expired_or_malformed_token(token_factory) -> None:
    with pytest.raises(HTTPException) as error:
        auth.decode_token(token_factory())

    assert error.value.detail in {"Token inválido", "Token inválido o expirado"}


def test_decode_token_rejects_token_without_subject() -> None:
    token = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        auth.SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )

    with pytest.raises(HTTPException) as error:
        auth.decode_token(token)

    assert error.value.detail == "Token inválido"


def test_reset_token_requires_reset_type() -> None:
    access_token = auth.create_access_token(42)

    with pytest.raises(HTTPException) as error:
        auth.decode_reset_token(access_token)

    assert error.value.detail == "Token inválido"


def test_reset_link_removes_duplicate_trailing_slash() -> None:
    link = auth.get_reset_link("token", "https://frontend.example/")

    assert link == "https://frontend.example/reset-password?token=token"