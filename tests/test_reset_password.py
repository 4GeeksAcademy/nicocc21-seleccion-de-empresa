import pytest
from fastapi import HTTPException

from services.brasaland_api.auth import create_reset_token
from services.brasaland_api.database import get_user_by_id, hash_token, store_reset_token
from services.brasaland_api.models import ResetPasswordRequest
from services.brasaland_api.routes.auth import reset_password


def test_reset_password_accepts_valid_token(user: dict[str, object]) -> None:
    token = create_reset_token(user["id"])
    store_reset_token(user["id"], hash_token(token), "9999-12-31T00:00:00+00:00")

    result = reset_password(
        ResetPasswordRequest(token=token, new_password="new-secret")
    )

    updated_user = get_user_by_id(user["id"])
    assert "restablecida correctamente" in result.message
    assert updated_user is not None


def test_reset_password_rejects_same_password(user: dict[str, object]) -> None:
    token = create_reset_token(user["id"])
    store_reset_token(user["id"], hash_token(token), "9999-12-31T00:00:00+00:00")

    with pytest.raises(HTTPException) as error:
        reset_password(ResetPasswordRequest(token=token, new_password="secret123"))

    assert "diferente" in error.value.detail


def test_reset_password_rejects_reused_or_malformed_token(
    user: dict[str, object],
) -> None:
    token = create_reset_token(user["id"])
    store_reset_token(user["id"], hash_token(token), "9999-12-31T00:00:00+00:00")
    payload = ResetPasswordRequest(token=token, new_password="new-secret")

    reset_password(payload)

    with pytest.raises(HTTPException) as reused_error:
        # El mismo token no debe poder consumirse dos veces.
        reset_password(payload)
    with pytest.raises(HTTPException) as malformed_error:
        reset_password(ResetPasswordRequest(token="malformed", new_password="new-secret"))

    assert "ya fue utilizado" in reused_error.value.detail
    assert "inválido o ha expirado" in malformed_error.value.detail