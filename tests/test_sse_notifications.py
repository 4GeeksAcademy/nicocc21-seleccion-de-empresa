"""
tests/test_sse_notifications.py — Tests del endpoint SSE de notificaciones RFP.

ESTRATEGIA DE TEST:
  - ``test_sse_health`` usa httpx contra la app real (funciona OK).
  - Los tests de streaming SSE llaman directamente al generador
    ``_event_stream`` con un Request simulado, evitando la complejidad
    de httpx + ASGITransport + StreamingResponse + cancelación.

  Esta separación permite verificar el contenido del flujo SSE sin
  depender del cleanup de conexiones ASGI.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from services.brasaland_api.auth import create_access_token
from services.brasaland_api.database import create_user
from services.brasaland_api.main import app
from services.brasaland_api.notifications import init_notification_manager, get_notification_manager
from services.brasaland_api.routes.sse import _event_stream


# ─── Mock de Request para pruebas directas del generador ──────────────

class FakeRequest:
    """Simula un ``fastapi.Request`` lo mínimo para que ``_event_stream`` funcione.

    ``is_disconnected()`` retorna ``True`` tras un número de iteraciones
    controlado, permitiendo que el generador termine limpiamente.
    """

    def __init__(self, max_iterations: int = 0) -> None:
        self._iteration = 0
        self._max = max_iterations

    async def is_disconnected(self) -> bool:
        self._iteration += 1
        return self._iteration > self._max


# ─── Helpers ──────────────────────────────────────────────────────────

async def _collect_stream(
    channel: str = "rfp",
    last_event_id: int | None = None,
    max_iterations: int = 0,
) -> list[str]:
    """Ejecuta ``_event_stream`` y devuelve las líneas SSE generadas.

    Args:
        channel: Canal SSE.
        last_event_id: Event-ID para replay.
        max_iterations: Iteraciones del bucle antes de que
                        ``FakeRequest.is_disconnected()`` retorne True.

    Returns:
        Lista de líneas SSE en orden.
    """
    lines: list[str] = []
    fake_req = FakeRequest(max_iterations=max_iterations)
    async for chunk in _event_stream(
        channel=channel,
        last_event_id=last_event_id,
        request=fake_req,
    ):
        lines.extend(chunk.decode("utf-8").split("\n"))
    return lines


# ─── Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_health() -> None:
    """GET /sse/health devuelve estado ok (endpoint no-streaming)."""
    init_notification_manager()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/sse/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "subscribers" in body


@pytest.mark.asyncio
async def test_sse_stream_structure() -> None:
    """El generador SSE produce chunks con el formato correcto (event + data)."""
    init_notification_manager()
    mgr = get_notification_manager()

    # Publicar un evento antes de conectar
    mgr.publish("rfp", "rfp_ticket_created", {
        "ticket_id": "tkt_0001",
        "rfp_id": "rfp_0001",
        "status": "analizando",
    })

    # Conectar con replay desde id=0 (recibe el evento y luego sale)
    lines = await _collect_stream(
        channel="rfp",
        last_event_id=0,
        max_iterations=3,  # replay + 2 polls → disconnected
    )

    # Verificar estructura SSE
    assert any(l.startswith("event: rfp_ticket_created") for l in lines), (
        "Debe contener event: rfp_ticket_created"
    )
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) == 1, f"Esperada 1 línea data, recibidas {len(data_lines)}"
    data = json.loads(data_lines[0].replace("data: ", "", 1))
    assert data["ticket_id"] == "tkt_0001"
    assert data["status"] == "analizando"

    # Verificar event-id presente
    assert any(l.startswith("id: ") for l in lines), "Debe contener event-id"


@pytest.mark.asyncio
async def test_sse_replay_on_reconnect() -> None:
    """Cliente con Last-Event-ID recibe eventos perdidos durante desconexión."""
    init_notification_manager()
    mgr = get_notification_manager()

    # Publicar 3 eventos
    ids: list[int] = []
    for i in range(3):
        eid = mgr.publish("rfp", "test_event", {"seq": i})
        ids.append(eid)

    # Conectar con last-event-id = ids[0] → recibe eventos 1 y 2 (seqs 1,2)
    lines = await _collect_stream(
        channel="rfp",
        last_event_id=ids[0],
        max_iterations=5,  # replay de 2 eventos + 3 polls → disconnected
    )

    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) >= 2, (
        f"Esperados al menos 2 data, recibidos {len(data_lines)}"
    )
    # Verificar que replay saltó el evento ids[0] (seq=0)
    first_data = json.loads(data_lines[0].replace("data: ", "", 1))
    assert first_data["seq"] == 1, (
        f"Primer evento replay debe ser seq=1, recibido seq={first_data['seq']}"
    )


@pytest.mark.asyncio
async def test_sse_stream_without_replay() -> None:
    """Sin Last-Event-ID el generador no hace replay, espera eventos en cola."""
    init_notification_manager()

    lines = await _collect_stream(
        channel="rfp",
        last_event_id=None,
        max_iterations=2,  # 2 polls → disconnected, sin eventos
    )

    # Sin replay ni eventos, solo debería tener heartbeats o nada
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) == 0, "Sin eventos publicados no debe haber data"
    # El stream puede producir heartbeats (comentarios) o estar vacío
    # Lo importante es que no falle y que se limpie correctamente


# ─── Tests de autenticación SSE ──────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_auth_required() -> None:
    """GET /sse/rfp/events sin token retorna 401."""
    init_notification_manager()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/sse/rfp/events")
        assert response.status_code == 401, (
            f"SSE sin auth debió retornar 401, obtuvo {response.status_code}"
        )
        body = response.json()
        assert "detail" in body


@pytest.mark.asyncio
async def test_sse_auth_invalid_token() -> None:
    """GET /sse/rfp/events con token inválido retorna 401."""
    init_notification_manager()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get(
            "/sse/rfp/events",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_sse_auth_with_valid_token_event_stream() -> None:
    """Con token válido, el generador SSE produce eventos correctamente.

    Este test crea un usuario, genera un token JWT, publica un evento
    y verifica que el generador SSE lo recibe (validación indirecta
    de que el endpoint SSE con auth funciona).
    """
    init_notification_manager()
    from services.brasaland_api.database import create_user
    from services.brasaland_api.auth import hash_password

    # Crear usuario con email único
    import uuid
    unique_email = f"sse-valid-{uuid.uuid4().hex[:8]}@example.com"
    user = create_user(
        email=unique_email,
        password_hash=hash_password("test-pass"),
    )
    token = create_access_token(user_id=user["id"])
    assert token, "El token debe generarse correctamente"

    # Verificar que el token es válido contra get_current_user
    from services.brasaland_api.auth import get_current_user
    from fastapi.security import OAuth2PasswordBearer
    from fastapi import Depends
    import httpx

    # Verificar que auth funciona: llamada directa a get_current_user
    # Simular la dependencia inyectando el token
    user_result = get_current_user(token=token)
    assert user_result is not None
    assert user_result["id"] == user["id"]

    # Publicar un evento y verificar que el generador SSE lo produce
    mgr = get_notification_manager()
    event_id = mgr.publish("rfp", "rfp_ticket_created", {
        "ticket_id": "tkt_0001",
        "rfp_id": "rfp_0001",
        "status": "analizando",
    })

    lines = await _collect_stream(
        channel="rfp",
        last_event_id=0,
        max_iterations=3,
    )

    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) >= 1, "Debe recibir al menos un evento SSE"
    data = json.loads(data_lines[0].replace("data: ", "", 1))
    assert data["ticket_id"] == "tkt_0001"
    assert data["status"] == "analizando"


# ─── Tests de formato de payload contra BRIEFING.md ──────────────────

@pytest.mark.asyncio
async def test_sse_payload_contains_briefing_fields() -> None:
    """El payload SSE incluye los campos definidos en BRIEFING.md (§2.3).

    Según el briefing, un evento SSE debe contener al menos: ticket_id, rfp_id,
    status, created_at. Los metadatos adicionales (client_name, location,
    service_type) se añadirán cuando el pipeline los extraiga.
    """
    init_notification_manager()
    mgr = get_notification_manager()

    mgr.publish("rfp", "rfp_ticket_created", {
        "ticket_id": "tkt_0192",
        "rfp_id": "rfp_0088",
        "client_name": "Sunset Bay Resorts",
        "location": "Florida, USA",
        "service_type": "concesión co-branded",
        "status": "analizando",
        "created_at": "2026-11-17T12:00:00",
    })

    lines = await _collect_stream(
        channel="rfp",
        last_event_id=0,
        max_iterations=3,
    )

    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) >= 1, "Debe haber al menos una línea data"
    data = json.loads(data_lines[0].replace("data: ", "", 1))

    # Campos obligatorios del briefing
    assert "ticket_id" in data, "Falta ticket_id (BRIEFING §2.3)"
    assert "rfp_id" in data, "Falta rfp_id (BRIEFING §2.3)"
    assert "status" in data, "Falta status (BRIEFING §2.3)"
    assert "created_at" in data, "Falta created_at (BRIEFING §2.3)"

    # Campos opcionales pero deseables según briefing
    if "client_name" in data:
        assert isinstance(data["client_name"], str)
    if "location" in data:
        assert isinstance(data["location"], str)
    if "service_type" in data:
        assert isinstance(data["service_type"], str)

    # Verificar tipo y formato
    assert data["ticket_id"].startswith("tkt_"), (
        f"ticket_id debe empezar con 'tkt_', obtuvo {data['ticket_id']}"
    )
    assert data["rfp_id"].startswith("rfp_"), (
        f"rfp_id debe empezar con 'rfp_', obtuvo {data['rfp_id']}"
    )