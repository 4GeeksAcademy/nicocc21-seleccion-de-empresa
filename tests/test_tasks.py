from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from data.pipelines.weekly_location_performance import PipelineAlreadyRunning
from services import celery_app as celery_module
from services.brasaland_api.routes import tasks as tasks_routes
from services.reporting import tasks as reporting_tasks


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(tasks_routes.router)
    return TestClient(app)


def fake_result(state: str, result: object = None) -> object:
    return lambda _task_id, app=None: SimpleNamespace(state=state, result=result)


@pytest.mark.parametrize("state", ["PENDING", "STARTED"])
def test_task_status_in_progress(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    monkeypatch.setattr(tasks_routes, "AsyncResult", fake_result(state))
    response = client.get("/tasks/abc")
    assert response.status_code == 200
    assert response.json() == {"task_id": "abc", "status": state.lower()}


def test_task_status_success_includes_result(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tasks_routes, "AsyncResult", fake_result("SUCCESS", [{"status": "completed"}]))
    body = client.get("/tasks/abc").json()
    assert body["status"] == "success"
    assert body["result"] == [{"status": "completed"}]


def test_task_status_failure_includes_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tasks_routes, "AsyncResult", fake_result("FAILURE", RuntimeError("boom")))
    body = client.get("/tasks/abc").json()
    assert body["status"] == "failure"
    assert body["error"] == "boom"


@pytest.fixture
def eager(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    dlq: list[dict[str, object]] = []

    def fake_dlq(task_id, task_name, attempt, error, args, kwargs) -> None:  # noqa: ANN001
        dlq.append({"task_id": task_id, "attempt": attempt, "error": error})

    monkeypatch.setattr(celery_module, "send_to_dlq", fake_dlq)
    monkeypatch.setattr(reporting_tasks, "recover_stale_pipeline_runs", lambda: 0)
    return dlq


def test_task_sends_to_dlq_after_three_failed_attempts(
    eager: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[date | None] = []

    def failing_flow(week_start: date | None, trigger: str):  # noqa: ANN202
        calls.append(week_start)
        raise RuntimeError("db down")

    monkeypatch.setattr(reporting_tasks, "weekly_location_performance_flow", failing_flow)
    result = reporting_tasks.run_weekly_pipeline.apply(args=["2026-10-19"], throw=False)

    assert result.failed()
    assert len(calls) == 3
    assert len(eager) == 1
    assert eager[0]["attempt"] == 3
    assert eager[0]["error"] == "db down"
    assert eager[0]["task_id"] == result.id


def test_task_succeeds_without_dlq(
    eager: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        reporting_tasks, "weekly_location_performance_flow",
        lambda week_start, trigger: [{"status": "completed"}],
    )
    result = reporting_tasks.run_weekly_pipeline.apply(args=[None])

    assert result.get() == [{"status": "completed"}]
    assert eager == []


def test_already_running_is_not_retried(
    eager: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def conflict(week_start, trigger):  # noqa: ANN001, ANN202
        calls.append(1)
        raise PipelineAlreadyRunning(date(2026, 10, 19))

    monkeypatch.setattr(reporting_tasks, "weekly_location_performance_flow", conflict)
    result = reporting_tasks.run_weekly_pipeline.apply(args=["2026-10-19"], throw=False)

    assert result.failed()
    assert len(calls) == 1
