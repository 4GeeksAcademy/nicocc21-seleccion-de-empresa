from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from data.pipelines import recovery


class FakeResult:
    rowcount = 2


class FakeConnection:
    def __init__(self) -> None:
        self.statement = None

    def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        return FakeResult()


class FakeTransaction:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeConnection:
        return self.connection

    def __exit__(self, *_args: object) -> None:
        return None


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def begin(self) -> FakeTransaction:
        return FakeTransaction(self.connection)


def test_recovery_fails_only_running_runs_past_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    connection = FakeConnection()
    monkeypatch.setattr(recovery, "ensure_reporting_tables", lambda: None)
    monkeypatch.setattr(recovery, "get_engine", lambda: FakeEngine(connection))

    recovered = recovery.recover_stale_pipeline_runs(now, stale_after_minutes=30)

    assert recovered == 2
    compiled = connection.statement.compile()
    assert "status" in str(compiled)
    assert any(value == "running" for value in compiled.params.values())
    assert any(
        value == now - timedelta(minutes=30)
        for value in compiled.params.values()
    )


def test_recovery_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="debe ser positivo"):
        recovery.recover_stale_pipeline_runs(stale_after_minutes=0)