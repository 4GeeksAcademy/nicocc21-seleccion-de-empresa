import pytest
from pydantic import ValidationError

from services.brasaland_api.models import ForgotPasswordRequest
from services.brasaland_api.routes import auth as auth_routes


def test_forgot_password_sends_email_for_existing_user(
    user: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_routes,
        "send_reset_email",
        lambda to_email, reset_link: sent.append((to_email, reset_link)),
    )

    result = auth_routes.forgot_password(
        ForgotPasswordRequest(email=str(user["email"]))
    )

    assert "recibirás un enlace" in result.message
    assert sent and sent[0][0] == user["email"]


def test_forgot_password_hides_unknown_email() -> None:
    first = auth_routes.forgot_password(
        ForgotPasswordRequest(email="unknown@example.com")
    )
    second = auth_routes.forgot_password(
        ForgotPasswordRequest(email="other@example.com")
    )

    assert first.message == second.message


def test_forgot_password_handles_empty_email_and_email_failure(
    user: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        ForgotPasswordRequest(email="")

    def failing_email(*_args, **_kwargs) -> None:
        raise RuntimeError("email service unavailable")

    monkeypatch.setattr(auth_routes, "send_reset_email", failing_email)
    result = auth_routes.forgot_password(
        ForgotPasswordRequest(email=str(user["email"]))
    )

    assert "recibirás un enlace" in result.message