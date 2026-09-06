from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from services.brasaland_api import database
from services.brasaland_api.auth import hash_password
from services.brasaland_api.database import create_user


@pytest.fixture
def test_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_file = tmp_path / "auth-tests.json"
    monkeypatch.setattr(database, "DB_FILE", db_file)
    return db_file


@pytest.fixture
def user(test_database: Path) -> dict[str, object]:
    return create_user(
        email="user@example.com",
        password_hash=hash_password("secret123"),
    )