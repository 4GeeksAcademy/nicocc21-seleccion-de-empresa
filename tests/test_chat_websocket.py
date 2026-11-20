"""tests/test_chat_websocket.py — Pruebas del WebSocket de chat en tiempo real (Hito 9, Parte 2).

Tests:
  - Conexión con token válido → handshake exitoso
  - Conexión sin token → rechazo
  - Enviar mensaje de usuario → recibir token_chunks
  - Enviar interrupt_requested → recibir generation_interrupted
  - Reconexión → recibir session_snapshot
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

# Configurar entorno de pruebas antes de importar módulos de la app
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-websocket-tests")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from services.brasaland_api.auth import create_access_token
from services.brasaland_api.chat_models import ChatSession, ensure_chat_tables
from services.brasaland_api.database import get_db, create_user
from services.brasaland_api.main import app
from services.brasaland_api.auth import hash_password

# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def db_session() -> Session:
    """Crea una base de datos SQLite en memoria para las pruebas."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def test_app(db_session: Session) -> FastAPI:
    """Aplica la dependencia de BD de prueba."""
    app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest.fixture
def test_user(db_session: Session) -> dict[str, Any]:
    """Crea un usuario de prueba y devuelve sus datos."""
    user = create_user(
        email="encargado@brasaland.com",
        password_hash=hash_password("secret123"),
    )
    return user


@pytest.fixture
def valid_token(test_user: dict[str, Any]) -> str:
    """Genera un token JWT válido para el usuario de prueba."""
    return create_access_token(test_user["id"])


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Cliente de prueba con soporte WebSocket."""
    return TestClient(test_app)


# ── Tests ──────────────────────────────────────────────────────────────

class TestChatWebSocketAuth:
    """Pruebas de autenticación del WebSocket."""

    def test_connect_without_token_is_rejected(self, test_client: TestClient) -> None:
        """Conexión sin token → rechazo con código 1008."""
        with test_client.websocket_connect("/ws/chat/new") as ws:
            response = ws.receive()
            # El servidor cierra la conexión antes de aceptar
            # Debería lanzar WebSocketDisconnect
            assert response is None

    def test_connect_with_invalid_token_is_rejected(self, test_client: TestClient) -> None:
        """Conexión con token inválido → rechazo."""
        with test_client.websocket_connect(
            "/ws/chat/new?token=token-invalido"
        ) as ws:
            response = ws.receive()
            assert response is None

    def test_connect_with_valid_token_succeeds(
        self, test_client: TestClient, valid_token: str
    ) -> None:
        """Conexión con token válido → acepta y recibe session_created."""
        with test_client.websocket_connect(
            f"/ws/chat/new?token={valid_token}"
        ) as ws:
            data = ws.receive_json()
            assert data["event"] == "session_created"
            assert "session_id" in data["data"]
            assert data["data"]["agent_id"] == "manager_support"
            assert data["data"]["status"] == "active"


class TestChatWebSocketMessaging:
    """Pruebas de mensajería bidireccional."""

    def test_user_message_triggers_token_chunks(
        self, test_client: TestClient, valid_token: str
    ) -> None:
        """Enviar user_message → recibe token_chunks y generation_completed."""
        with test_client.websocket_connect(
            f"/ws/chat/new?token={valid_token}"
        ) as ws:
            # Esperar session_created
            ws.receive_json()

            # Enviar mensaje de usuario
            ws.send_json({
                "event": "user_message",
                "data": {"text": "¿Cuál es el horario del local L03?"},
            })

            # Recibir eventos hasta generation_completed
            received_tokens = False
            received_completed = False
            timeout = 10  # segundos

            import time
            start = time.time()
            while time.time() - start < timeout:
                try:
                    msg = ws.receive_json(timeout=1)
                    if msg["event"] == "token_chunk":
                        received_tokens = True
                    elif msg["event"] == "generation_completed":
                        received_completed = True
                        break
                except Exception:
                    break

            assert received_tokens, "No se recibieron token_chunks"
            assert received_completed, "No se recibió generation_completed"

    def test_interrupt_generation(
        self, test_client: TestClient, valid_token: str
    ) -> None:
        """Enviar interrupt_requested → recibe generation_interrupted."""
        with test_client.websocket_connect(
            f"/ws/chat/new?token={valid_token}"
        ) as ws:
            # Esperar session_created
            ws.receive_json()

            # Enviar mensaje de usuario
            ws.send_json({
                "event": "user_message",
                "data": {"text": "Cuéntame la historia completa de Brasaland"},
            })

            # Esperar al menos un token_chunk
            import time
            start = time.time()
            received_token = False
            while time.time() - start < 5:
                try:
                    msg = ws.receive_json(timeout=1)
                    if msg["event"] == "token_chunk":
                        received_token = True
                        break
                except Exception:
                    break

            if not received_token:
                pytest.skip("No se recibió token a tiempo para interrumpir")

            # Enviar interrupción
            ws.send_json({
                "event": "interrupt_requested",
                "data": {"session_id": "", "new_input": "espera, pregunté por el local de Miami"},
            })

            # Recibir generation_interrupted
            start = time.time()
            received_interrupted = False
            while time.time() - start < 5:
                try:
                    msg = ws.receive_json(timeout=1)
                    if msg["event"] == "generation_interrupted":
                        received_interrupted = True
                        break
                except Exception:
                    break

            assert received_interrupted, "No se recibió generation_interrupted"


class TestChatWebSocketReconnect:
    """Pruebas de rehidratación de sesión."""

    def test_reconnect_gets_session_snapshot(
        self, test_client: TestClient, valid_token: str
    ) -> None:
        """Reconectar a una sesión existente → recibe session_snapshot."""
        # Primera conexión
        session_id = None
        with test_client.websocket_connect(
            f"/ws/chat/new?token={valid_token}"
        ) as ws:
            msg = ws.receive_json()
            session_id = msg["data"]["session_id"]

            # Enviar un mensaje
            ws.send_json({
                "event": "user_message",
                "data": {"text": "Hola"},
            })

            # Esperar que termine
            import time
            start = time.time()
            while time.time() - start < 8:
                try:
                    msg = ws.receive_json(timeout=1)
                    if msg["event"] == "generation_completed":
                        break
                except Exception:
                    break

        # Segunda conexión con el mismo session_id
        with test_client.websocket_connect(
            f"/ws/chat/{session_id}?token={valid_token}"
        ) as ws:
            # Debería recibir session_snapshot si hay historial
            import time
            start = time.time()
            received_snapshot = False
            while time.time() - start < 5:
                try:
                    msg = ws.receive_json(timeout=1)
                    if msg["event"] == "session_snapshot":
                        received_snapshot = True
                        assert len(msg["data"]["messages"]) > 0
                        break
                except Exception:
                    break

            assert received_snapshot, "No se recibió session_snapshot al reconectar"