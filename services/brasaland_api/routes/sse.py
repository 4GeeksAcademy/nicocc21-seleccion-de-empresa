"""
services/brasaland_api/routes/sse.py — Endpoint SSE para notificaciones en tiempo real.

Endpoints:
  GET  /sse/rfp/events  →  Stream SSE de eventos del ciclo de vida de RFP
  GET  /sse/health      →  Estado del sistema SSE (útil para debugging)

Uso:
  El NotificationManager usa colas síncronas (queue.Queue) para que tanto
  código síncrono (threads del pipeline) como asíncrono puedan publicar.
  El stream SSE adapta las colas síncronas con asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from services.brasaland_api.auth import get_current_user
from services.brasaland_api.notifications import get_notification_manager

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])

# ─── Constantes ────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL = 30.0       # segundos entre heartbeats

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Type": "text/event-stream",
}


# ─── Formateo SSE ─────────────────────────────────────────────────────

def _format_sse(event: str, data: dict[str, Any], event_id: int | None = None) -> bytes:
    """Formatea un evento SSE según el formato estándar.

    Formato:
        id: <event_id>
        event: <event_name>
        data: <json_line>
        \\n
    """
    lines: list[bytes] = []
    if event_id is not None:
        lines.append(f"id: {event_id}\n".encode("utf-8"))
    lines.append(f"event: {event}\n".encode("utf-8"))
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    for line in data_json.split("\n"):
        lines.append(f"data: {line}\n".encode("utf-8"))
    lines.append(b"\n")
    return b"".join(lines)


def _format_heartbeat() -> bytes:
    """Comentario SSE usado como heartbeat."""
    return b": heartbeat\n\n"


# ─── Stream SSE ────────────────────────────────────────────────────────

async def _event_stream(
    channel: str,
    last_event_id: int | None,
    request: Request,
) -> AsyncGenerator[bytes, None]:
    """Generador asíncrono que produce el flujo SSE.

    Args:
        channel: Canal de notificaciones a suscribirse.
        last_event_id: ID del último evento recibido por el cliente (para replay).
        request: Objeto Request de FastAPI para detectar desconexión.
    """
    manager = get_notification_manager()

    # Replay de eventos perdidos durante la desconexión
    if last_event_id is not None:
        replay_events = manager.replay_from(channel, last_event_id)
        for ev in replay_events:
            yield _format_sse(ev["event"], ev["data"], ev["id"])
            await asyncio.sleep(0.01)

    # Suscribirse al canal (thread-safe, devuelve queue.Queue síncrona)
    sync_queue = manager.subscribe(channel)
    _logger.info(
        "Cliente SSE conectado al canal '%s' (replay_from=%s)",
        channel, last_event_id,
    )

    # ─── Bucle principal ──────────────────────────────────────────
    # Usamos polling corto (POLL_INTERVAL) para poder comprobar
    # desconexión del cliente rápidamente (≈1s vs 30s del heartbeat).
    # El heartbeat se envía cada HEARTBEAT_INTERVAL acumulando polls vacíos.
    POLL_INTERVAL = 1.0
    seconds_since_heartbeat = 0.0

    try:
        while True:
            # Comprobar si el cliente sigue conectado
            if await request.is_disconnected():
                _logger.debug("Cliente SSE desconectado del canal '%s'", channel)
                break

            # Polling no-bloqueante de la cola síncrona
            event: dict[str, Any] | None = None
            try:
                event = sync_queue.get(block=False)
            except Exception:
                pass  # queue.Empty → no hay evento

            if event is not None:
                yield _format_sse(event["event"], event["data"], event["id"])
                seconds_since_heartbeat = 0.0
            else:
                seconds_since_heartbeat += POLL_INTERVAL
                if seconds_since_heartbeat >= HEARTBEAT_INTERVAL:
                    yield _format_heartbeat()
                    seconds_since_heartbeat = 0.0

            # Pausa corta para no saturar CPU (también cede el ciclo de eventos)
            await asyncio.sleep(POLL_INTERVAL)

    except asyncio.CancelledError:
        _logger.debug("Stream SSE cancelado para canal '%s'", channel)
    except Exception:
        _logger.exception("Error en stream SSE del canal '%s'", channel)
    finally:
        manager.unsubscribe(channel, sync_queue)
        _logger.debug("Suscripción liberada para canal '%s'", channel)


# ─── Endpoints ─────────────────────────────────────────────────────────

@router.get("/rfp/events")
async def sse_rfp_events(
    request: Request,
    last_event_id: int | None = Header(default=None, alias="last-event-id"),
    channel: str = Query(default="rfp", description="Canal SSE (por defecto 'rfp')"),
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """Stream SSE de eventos de tickets RFP.

    El cliente se conecta con:
        GET /sse/rfp/events

    Recibe eventos:
        event: rfp_ticket_created
        data: {"ticket_id": "tkt_0192", "rfp_id": "rfp_0088", "status": "analizando", ...}

    Args:
        request: Request de FastAPI (para detectar desconexión).
        last_event_id: Último event-id recibido por el cliente (para replay).
        channel: Canal SSE (query param opcional, default "rfp").
        current_user: Usuario autenticado (JWT).
    """
    return StreamingResponse(
        _event_stream(channel=channel, last_event_id=last_event_id, request=request),
        headers=SSE_HEADERS,
        media_type="text/event-stream",
    )


@router.get("/health")
async def sse_health() -> dict[str, Any]:
    """Estado del sistema SSE."""
    manager = get_notification_manager()
    return {
        "status": "ok",
        "subscribers": manager.subscriber_count,
    }