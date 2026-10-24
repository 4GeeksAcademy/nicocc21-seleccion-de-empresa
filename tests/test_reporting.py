from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.brasaland_api.database import get_db
from services.reporting import routes
from services.reporting.routes import router


class FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows

    def first(self) -> dict[str, object] | None:
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, rows: list[dict[str, object]] | None = None, latest_week: date | None = None) -> None:
        self.rows = rows or []
        self.latest_week = latest_week

    def exec(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(one=lambda: self.latest_week)

    def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self.rows)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    session = FakeSession(
        rows=[
            {
                "location_id": "L01",
                "country": "CO",
                "total_purchase_cost": Decimal("100.00"),
                "total_waste_cost": Decimal("7.00"),
                "waste_ratio": Decimal("0.070000"),
                "stockout_events_count": 2,
                "price_alert_events_count": 1,
                "currency": "COP",
            }
        ],
        latest_week=date(2026, 10, 19),
    )

    def get_test_session():
        yield session

    app.dependency_overrides[get_db] = get_test_session
    monkeypatch.setattr(routes, "recover_stale_pipeline_runs", lambda: 0)
    return TestClient(app)


def test_weekly_report_returns_all_business_kpis(client: TestClient) -> None:
    response = client.get("/reporting/weekly-location-performance?week_start=2026-10-19")

    assert response.status_code == 200
    report = response.json()
    assert report["week_start"] == "2026-10-19"
    location = report["locations"][0]
    assert location["location_id"] == "L01"
    assert location["country"] == "CO"
    assert location["total_purchase_cost"] == pytest.approx(100)
    assert location["total_waste_cost"] == pytest.approx(7)
    assert location["waste_ratio"] == pytest.approx(0.07)
    assert location["stockout_events_count"] == 2
    assert location["price_alert_events_count"] == 1
    assert location["currency"] == "COP"


def test_weekly_report_defaults_to_latest_calculated_week(client: TestClient) -> None:
    response = client.get("/reporting/weekly-location-performance")
    assert response.status_code == 200
    assert response.json()["week_start"] == "2026-10-19"


def test_weekly_report_rejects_non_monday(client: TestClient) -> None:
    response = client.get("/reporting/weekly-location-performance?week_start=2026-10-20")
    assert response.status_code == 422


def test_latest_pipeline_run_returns_run_metadata(client: TestClient) -> None:
    run_id = uuid4()
    started_at = datetime(2026, 10, 26, tzinfo=timezone.utc)
    session = FakeSession(rows=[{"run_id": run_id, "started_at": started_at, "status": "completed"}])

    def get_run_session():
        yield session

    client.app.dependency_overrides[get_db] = get_run_session

    response = client.get("/reporting/pipeline-runs/latest")
    assert response.status_code == 200
    assert response.json()["run_id"] == str(run_id)
    assert response.json()["status"] == "completed"


def test_manual_run_invokes_flow(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_flow(week_start: date | None, trigger: str) -> list[dict[str, object]]:
        captured.update(week_start=week_start, trigger=trigger)
        return [{"status": "completed"}]

    monkeypatch.setattr(routes, "weekly_location_performance_flow", fake_flow)
    response = client.post("/reporting/pipeline-runs", json={"week_start": "2026-10-19"})

    assert response.status_code == 200
    assert captured == {"week_start": date(2026, 10, 19), "trigger": "manual"}


def test_manual_run_returns_conflict_for_active_week(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def already_running(_week_start: date | None, trigger: str) -> list[dict[str, object]]:
        raise routes.PipelineAlreadyRunning(date(2026, 10, 19))

    monkeypatch.setattr(routes, "weekly_location_performance_flow", already_running)
    response = client.post("/reporting/pipeline-runs", json={"week_start": "2026-10-19"})

    assert response.status_code == 409