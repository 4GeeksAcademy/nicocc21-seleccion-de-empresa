import pytest
from fastapi import HTTPException

from services.brasaland_api import auth
from services.brasaland_api.database import get_user_by_id
from services.brasaland_api.models import ChangePasswordRequest
from services.brasaland_api.routes.auth import change_password


def test_change_password_updates_password(user: dict[str, object]) -> None:
    result = change_password(
        ChangePasswordRequest(current_password="secret123", new_password="new-secret"),
        user,
    )

    updated_user = get_user_by_id(user["id"])
    assert "actualizada correctamente" in result.message
    assert updated_user is not None
    # Leer el hash persistido confirma que la contraseña realmente cambió.
    assert auth.verify_password("new-secret", updated_user["password_hash"])


def test_change_password_rejects_reusing_current_password(
    user: dict[str, object],
) -> None:
    with pytest.raises(HTTPException) as error:
        change_password(
            ChangePasswordRequest(current_password="secret123", new_password="secret123"),
            user,
        )

    assert "diferente" in error.value.detail


def test_change_password_rejects_wrong_password_or_missing_session(
    user: dict[str, object],
) -> None:
    with pytest.raises(HTTPException) as error:
        change_password(
            ChangePasswordRequest(current_password="wrong", new_password="new-secret"),
            user,
        )

    assert error.value.detail == "La contraseña actual no es correcta."