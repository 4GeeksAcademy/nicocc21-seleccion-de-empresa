from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from services.brasaland_api import auth
from services.brasaland_api.database import create_profile
from services.brasaland_api.routes.auth import get_me


def test_me_returns_profile_for_valid_token(user: dict[str, object]) -> None:
    create_profile(user["id"], {"full_name": "Test User"})
    result = get_me(user)

    assert result.profile is not None
    assert result.profile.full_name == "Test User"
    assert not hasattr(result, "password_hash")


def test_me_allows_user_without_profile(user: dict[str, object]) -> None:
    result = get_me(user)

    assert result.profile is None


def test_me_rejects_expired_token(user: dict[str, object]) -> None:
    expired_token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        auth.SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(expired_token)

    assert error.value.detail == "Token inválido o expirado"