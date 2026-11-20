"""services/brasaland_api/routes/chat_ws.py — WebSocket endpoint de chat en tiempo real (Hito 9, Parte 2).

Expone el Manager Support Agent vía WebSocket bidireccional.

Eventos del servidor al cliente:
  - token_chunk: un token de la respuesta del agente
  - generation_completed: la generación terminó exitosamente
  - generation_interrupted: la generación fue abortada por el usuario
  - session_snapshot: historial de la sesión (para rehidratación)

Eventos del cliente al servidor:
  - user_message: un mensaje del usuario
  - interrupt_requested: el usuario quiere interrumpir la generación

Autenticación vía JWT en query param ``?token=``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session, select

from services.brasaland_api.auth import decode_token
from services.brasaland_api.chat_models import ChatSession, ensure_chat_tables
from services.brasaland_api.chat_pubsub import ChatEvent, ChatPubSub
from services.brasaland_api.database import engine
from services.brasaland_api.agent import stream_agent_tokens

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Almacén en memoria del historial de mensajes por sesión (para rehidratación)
_session_messages: dict[str, list[dict[str, Any]]] = {}


# ─── Helper: validar JWT ──────────────────────────────────────────────

async def _validate_ws_token(websocket: WebSocket) -> dict | None:
    """Extrae y valida el token JWT de la query string.

    Returns:
        El usuario decodificado, o None si el token es inválido.
    """
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        user_id = decode_token(token)
        # Obtener usuario desde la base de datos
        from services.brasaland_api.database import get_user_by_id
        user = get_user_by_id(user_id)
        return user
    except Exception:
        return None


# ─── Helper: crear/recuperar sesión ───────────────────────────────────

def _get_or_create_session(
    session_id: str | None,
    user: dict,
    db_session: Session,
) -> ChatSession:
    """Recupera una sesión existente o crea una nueva."""
    if session_id:
        session = db_session.get(ChatSession, session_id)
        if session:
            if session.status == "closed":
                # Si está cerrada, crear una nueva
                pass
            else:
                return session

    # Crear nueva sesión
    new_session = ChatSession(
        session_id=session_id or str(uuid4()),
        agent_id="manager_support",
        user_id=user.get("id"),
        location_id=None,  # Se puede setear vía mensaje de sistema
        status="active",
    )
    db_session.add(new_session)
    db_session.commit()
    db_session.refresh(new_session)
    return new_session


# ─── Helper: enviar evento JSON al WebSocket ──────────────────────────

async def _send_event(websocket: WebSocket, event: str, data: dict[str, Any]) -> None:
    """Envía un evento JSON al WebSocket."""
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    try:
        await websocket.send_text(payload)
    except Exception as exc:
        _logger.warning("Error al enviar evento %s: %s", event, exc)


# ─── Endpoint WebSocket ───────────────────────────────────────────────

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """Conexión WebSocket bidireccional para chat con el agente de soporte.

    Args:
        websocket: Conexión WebSocket.
        session_id: UUID de la sesión de chat. Si es 'new', se crea una nueva.
    """
    # ── 1. Autenticación ──────────────────────────────────────────
    user = await _validate_ws_token(websocket)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        _logger.warning("Conexión WebSocket rechazada: token inválido o faltante")
        return

    # ── 2. Aceptar conexión ───────────────────────────────────────
    await websocket.accept()
    _logger.info(
        "WebSocket conectado: session=%s, user=%s",
        session_id, user.get("id"),
    )

    # ── 3. Crear o recuperar sesión (BD manual, sin Depends) ─────
    db_session = Session(engine)
    try:
        resolved_session_id = session_id if session_id != "new" else None
        chat_session = _get_or_create_session(resolved_session_id, user, db_session)
        sid = chat_session.session_id

        if session_id == "new":
            # Enviar el session_id real al cliente
            await _send_event(websocket, "session_created", {
                "session_id": sid,
                "agent_id": chat_session.agent_id,
                "status": chat_session.status,
            })

        # ── 4. Suscribirse al Pub/Sub ─────────────────────────────────
        pubsub = ChatPubSub()
        queue = await pubsub.subscribe(sid)

        # ── 5. Rehidratación: enviar snapshot si hay historial ────────
        messages = _session_messages.get(sid, [])
        if messages:
            await _send_event(websocket, "session_snapshot", {
                "session_id": sid,
                "messages": messages,
            })

        # ── 6. Task de consumo de Pub/Sub ─────────────────────────────
        async def _consume_pubsub():
            try:
                while True:
                    event = await queue.get()
                    await _send_event(websocket, event.event, event.data)
            except asyncio.CancelledError:
                pass
            except Exception:
                _logger.exception("Error en consumer pubsub")

        consumer_task = None

        try:
            consumer_task = asyncio.create_task(_consume_pubsub())

            # ── 7. Loop principal: recibir mensajes del cliente ────────
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    _logger.warning("JSON inválido recibido: %s", raw[:100])
                    continue

                event = payload.get("event")
                data = payload.get("data", {})
                text = data.get("text", "") if isinstance(data, dict) else ""

                if event == "user_message":
                    if not text.strip():
                        continue

                    # Guardar en historial en memoria
                    _session_messages.setdefault(sid, []).append({
                        "role": "user",
                        "content": text,
                    })

                    # Marcar sesión como activa
                    if chat_session.status != "active":
                        chat_session.status = "active"
                        db_session.add(chat_session)
                        db_session.commit()

                    # Disparar el agente en streaming (en una task separada)
                    asyncio.create_task(
                        stream_agent_tokens(text, sid)
                    )

                elif event == "interrupt_requested":
                    _logger.info("Interrupción solicitada por el usuario en sesión %s", sid)
                    chat_session.status = "interrupted"
                    db_session.add(chat_session)
                    db_session.commit()
                    await pubsub.request_cancel(sid)

                    # Publicar el nuevo input del usuario si viene
                    new_input = data.get("new_input", "") if isinstance(data, dict) else ""
                    if new_input.strip():
                        _session_messages.setdefault(sid, []).append({
                            "role": "user",
                            "content": new_input,
                        })

                else:
                    _logger.debug("Evento desconocido del cliente: %s", event)

        except WebSocketDisconnect:
            _logger.info("WebSocket desconectado: session=%s", sid)
        except Exception as exc:
            _logger.exception("Error en WebSocket session=%s: %s", sid, exc)
        finally:
            # Limpiar Pub/Sub y consumer
            if consumer_task is not None:
                consumer_task.cancel()
            await pubsub.unsubscribe(sid, queue)
            # Cerrar sesión en BD
            try:
                chat_session.status = "closed"
                db_session.add(chat_session)
                db_session.commit()
            except Exception:
                pass
            _logger.info("Sesión %s cerrada", sid)
    finally:
        db_session.close()