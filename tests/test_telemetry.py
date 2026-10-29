from __future__ import annotations

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.brasaland_api.database import get_db
from services.brasaland_api.inventory_models import TelemetryEventRecord
from services.brasaland_api.routes.telemetry import router
from services.brasaland_api.telemetry import MAX_BATCH_BYTES


class RecordingSession:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[object, list[dict[str, object]]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, statement: object, records: list[dict[str, object]]) -> None:
        self.execute_calls.append((statement, records))

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.fixture
def telemetry_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    session = RecordingSession()

    def get_test_session():
        yield session

    app.dependency_overrides[get_db] = get_test_session
    app.state.telemetry_session = session
    return TestClient(app)


@pytest.fixture
def section_event() -> dict[str, object]:
    return {
        "eventId": str(uuid4()),
        "timestamp": "2026-10-15T12:00:00Z",
        "sessionId": str(uuid4()),
        "userId": None,
        "event_type": "section_viewed",
        "schemaVersion": "1.0.0",
        "requestId": str(uuid4()),
        "properties": {"section_code": "inventory_products"},
    }


def test_storage_model_has_contract_columns_and_analytical_indexes() -> None:
    table = TelemetryEventRecord.__table__
    assert set(table.columns.keys()) == {
        "event_id", "timestamp", "session_id", "user_id", "event_type",
        "schema_version", "request_id", "service", "tags",
    }

    indexes = {index.name: index for index in table.indexes}
    assert len(indexes) == 3
    assert any([column.name for column in index.columns] == ["timestamp"] for index in indexes.values())
    assert any([column.name for column in index.columns] == ["event_type"] for index in indexes.values())
    tags_index = next(index for index in indexes.values() if [column.name for column in index.columns] == ["tags"])
    assert tags_index.dialect_options["postgresql"]["using"] == "gin"


@pytest.mark.parametrize("count", [1, 2, 20])
def test_accepts_valid_batches(
    telemetry_client: TestClient, section_event: dict[str, object], count: int
) -> None:
    events = [{**section_event, "eventId": str(uuid4())} for _ in range(count)]
    response = telemetry_client.post("/telemetry/events", json={"events": events})
    assert response.status_code == 200
    assert response.json() == {"received": count, "stored": count, "rejected": 0}
    session = telemetry_client.app.state.telemetry_session
    assert len(session.execute_calls) == 1
    assert len(session.execute_calls[0][1]) == count
    assert session.commit_calls == 1
    assert session.execute_calls[0][1][0]["service"] == "brasaland-api"
    assert session.execute_calls[0][1][0]["tags"] == events[0]["properties"]


@pytest.mark.parametrize(
    "change",
    [
        {"eventId": "not-a-uuid"},
        {"sessionId": "not-a-uuid"},
        {"requestId": "not-a-uuid"},
        {"timestamp": "2026-99-15T12:00:00Z"},
        {"timestamp": "2026-10-15T12:00:00+00:00"},
        {"schemaVersion": "2.0.0"},
        {"event_type": "unknown_event"},
        {"properties": {"section_code": "inventory_products", "email": "secret"}},
        {"userId": "private@example.com"},
        {"unexpected": "secret"},
        {"properties": {}},
    ],
)
def test_rejects_invalid_events_without_losing_valid_events(
    telemetry_client: TestClient,
    section_event: dict[str, object],
    change: dict[str, object],
) -> None:
    response = telemetry_client.post(
        "/telemetry/events", json={"events": [section_event, {**section_event, **change}]}
    )
    assert response.status_code == 200
    assert response.json() == {"received": 2, "stored": 1, "rejected": 1}
    session = telemetry_client.app.state.telemetry_session
    assert len(session.execute_calls) == 1
    assert len(session.execute_calls[0][1]) == 1
    assert session.commit_calls == 1


@pytest.mark.parametrize("field", ["timestamp", "userId", "properties", "requestId"])
def test_rejects_missing_required_fields(
    telemetry_client: TestClient, section_event: dict[str, object], field: str
) -> None:
    del section_event[field]
    response = telemetry_client.post("/telemetry/events", json={"events": [section_event]})
    assert response.status_code == 422


@pytest.mark.parametrize("payload", [{}, {"events": {}}, [], None])
def test_rejects_invalid_batch_envelope(
    telemetry_client: TestClient, payload: object
) -> None:
    response = telemetry_client.post(
        "/telemetry/events", content=json.dumps(payload), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_rejects_extra_batch_fields_and_excess_events(
    telemetry_client: TestClient, section_event: dict[str, object]
) -> None:
    for payload in (
        {"events": [section_event], "token": "secret"},
        {"events": [section_event] * 21},
    ):
        response = telemetry_client.post("/telemetry/events", json=payload)
        assert response.status_code == 422
        assert "secret" not in response.text


def test_accepts_empty_event_array(telemetry_client: TestClient) -> None:
    response = telemetry_client.post("/telemetry/events", json={"events": []})
    assert response.status_code == 200
    assert response.json() == {"received": 0, "stored": 0, "rejected": 0}
    assert telemetry_client.app.state.telemetry_session.execute_calls == []


def test_telemetry_route_is_append_only(telemetry_client: TestClient) -> None:
    routes = [route for route in telemetry_client.app.routes if getattr(route, "path", None) == "/telemetry/events"]
    assert len(routes) == 1
    assert routes[0].methods == {"POST"}


@pytest.mark.parametrize("body", [b"{", b"\xff", b"NaN", b"Infinity", b"-Infinity", b"1e400"])
def test_rejects_invalid_json(telemetry_client: TestClient, body: bytes) -> None:
    response = telemetry_client.post(
        "/telemetry/events", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "INVALID_JSON"}


def test_enforces_byte_limit(
    telemetry_client: TestClient, section_event: dict[str, object]
) -> None:
    encoded = json.dumps({"events": [section_event]}).encode("utf-8")
    body = encoded + b" " * (MAX_BATCH_BYTES - len(encoded))
    for content, expected in ((body, 200), (body + b" ", 413)):
        response = telemetry_client.post(
            "/telemetry/events", content=content, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == expected


def test_requires_json_content_type(telemetry_client: TestClient) -> None:
    response = telemetry_client.post("/telemetry/events", content="{}")
    assert response.status_code == 415


def test_validates_business_event_country_and_currency(
    telemetry_client: TestClient, section_event: dict[str, object]
) -> None:
    event = {
        **section_event,
        "userId": "42",
        "event_type": "inbound_order_created",
        "properties": {
            "location_id": "L01", "country": "CO", "product_id": "1",
            "product_category": "meat", "quantity": 2, "unit": "kg", "currency": "COP",
            "order_id": "1", "supplier_id": "2", "unit_price": "10.00", "total_amount": "20.00",
        },
    }
    valid_response = telemetry_client.post("/telemetry/events", json={"events": [event]})
    assert valid_response.status_code == 200
    assert valid_response.json() == {"received": 1, "stored": 1, "rejected": 0}
    invalid = deepcopy(event)
    invalid["properties"]["currency"] = "USD"
    invalid_response = telemetry_client.post("/telemetry/events", json={"events": [invalid]})
    assert invalid_response.status_code == 200
    assert invalid_response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_does_not_log_event_payload(
    telemetry_client: TestClient,
    section_event: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = telemetry_client.post("/telemetry/events", json={"events": [section_event]})
    assert response.status_code == 200
    assert section_event["eventId"] not in caplog.text