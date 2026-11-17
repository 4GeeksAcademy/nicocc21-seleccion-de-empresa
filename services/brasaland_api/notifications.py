"""
services/brasaland_api/notifications.py — Gestor de notificaciones pub/sub.

Usa ``queue.Queue`` (thread-safe) internamente para que tanto código síncrono
(threads del pipeline) como asíncrono (SSE endpoint) puedan publicar eventos.
La suscripción desde el endpoint SSE adapta la cola síncrona con
``asyncio.to_thread``.

Canales predefinidos:
  - "rfp"       → eventos del ciclo de vida de tickets RFP
  - "sales"     → alertas de caída de ventas (opcional)
  - "location"  → alertas de inactividad de ubicaciones (opcional)

Eventos:
  Cada evento es un dict con:
    - id: int (monotónico, para Last-Event-ID)
    - event: str (nombre del evento SSE, ej. "rfp_ticket_created")
    - data: dict (payload del evento)
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
from typing import Any

_logger = logging.getLogger(__name__)

# ─── Configuración ─────────────────────────────────────────────────────
MAX_HISTORY_PER_CHANNEL = 50  # eventos para replay en reconexión


class NotificationManager:
    """Gestor central de notificaciones pub/sub (thread-safe).

    Tanto ``publish`` como ``subscribe``/``unsubscribe`` son thread-safe.
    ``publish`` puede llamarse desde hilos (threading) o desde código async.
    ``subscribe`` devuelve una ``queue.Queue`` síncrona; el SSE endpoint
    la adapta con ``asyncio.to_thread()``.
    """

    def __init__(self) -> None:
        self._counter = itertools.count(1)
        # { "rfp": { <queue_id>: queue.Queue, ... }, ... }
        self._subscribers: dict[str, dict[int, queue.Queue]] = {}
        # { "rfp": [ {id, event, data}, ... ] }  — histórico circular
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ─── Suscripción ─────────────────────────────────────────────────

    def subscribe(self, channel: str) -> queue.Queue:
        """Abre una cola de suscripción a un canal (thread-safe).

        El suscriptor debe llamar a ``unsubscribe`` cuando cierre la conexión.
        Devuelve una ``queue.Queue`` síncrona.
        """
        q: queue.Queue = queue.Queue()
        with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = {}
                self._history[channel] = []
            qid = id(q)
            self._subscribers[channel][qid] = q
        _logger.debug("Suscriptor añadido al canal '%s' (total: %d)", channel, len(self._subscribers[channel]))
        return q

    def unsubscribe(self, channel: str, q: queue.Queue) -> None:
        """Cierra una suscripción (thread-safe)."""
        qid = id(q)
        with self._lock:
            subs = self._subscribers.get(channel)
            if subs and qid in subs:
                del subs[qid]
                _logger.debug("Suscriptor eliminado del canal '%s' (quedan: %d)", channel, len(subs))

    # ─── Publicación ──────────────────────────────────────────────────

    def publish(self, channel: str, event: str, data: dict[str, Any]) -> int:
        """Publica un evento en un canal (thread-safe).

        Args:
            channel: Nombre del canal (ej. "rfp").
            event: Nombre del evento SSE (ej. "rfp_ticket_created").
            data: Payload del evento.

        Returns:
            El ID asignado al evento (monotónico, para Last-Event-ID).
        """
        event_id = next(self._counter)
        payload: dict[str, Any] = {
            "id": event_id,
            "event": event,
            "data": data,
        }

        with self._lock:
            # Historial circular (siempre, incluso sin suscriptores)
            if channel not in self._history:
                self._history[channel] = []
            history = self._history[channel]
            history.append(payload)
            if len(history) > MAX_HISTORY_PER_CHANNEL:
                history.pop(0)

            # Distribuir a suscriptores
            subs = self._subscribers.get(channel)
            if subs:
                dead_queues: list[int] = []
                for qid, q in subs.items():
                    try:
                        q.put_nowait(payload)
                    except queue.Full:
                        _logger.warning("Cola llena para suscriptor %d en canal '%s' — descartando evento", qid, channel)
                        dead_queues.append(qid)
                for qid in dead_queues:
                    del subs[qid]

        _logger.debug("Evento #%d publicado en canal '%s': %s", event_id, channel, event)
        return event_id

    # ─── Replay ───────────────────────────────────────────────────────

    def replay_from(self, channel: str, last_event_id: int | None) -> list[dict[str, Any]]:
        """Devuelve los eventos desde ``last_event_id`` (exclusivo) para reconexión.

        Si ``last_event_id`` es None, devuelve lista vacía (el cliente nuevo
        no necesita replay; los eventos llegarán en tiempo real).
        """
        if last_event_id is None:
            return []
        with self._lock:
            history = self._history.get(channel, [])
        return [ev for ev in history if ev["id"] > last_event_id]

    # ─── Estadísticas ─────────────────────────────────────────────────

    @property
    def subscriber_count(self) -> dict[str, int]:
        """Número de suscriptores activos por canal."""
        with self._lock:
            return {ch: len(subs) for ch, subs in self._subscribers.items()}


# ─── Instancia global (singleton) ──────────────────────────────────────
# Se inicializa en el lifespan de la aplicación.
_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager:
    """Devuelve la instancia global del gestor de notificaciones."""
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager


def init_notification_manager() -> NotificationManager:
    """Inicializa (o reinicia) el gestor. Usar en lifespan startup."""
    global _manager
    _manager = NotificationManager()
    return _manager