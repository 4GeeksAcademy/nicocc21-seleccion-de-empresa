"""Pub/Sub en memoria para canales de chat en tiempo real (Hito 9, Parte 2).

Desacopla el productor (agente generando tokens) de los consumidores
(conexiones WebSocket). Usa `asyncio.Queue` por sesión — suficiente para
una implementación en un solo proceso sin Redis.

Cada sesión tiene:
  - Un canal `chat.<session_id>` al que se publican eventos.
  - Una cola (`asyncio.Queue`) por suscriptor.
  - Una señal de cancelación (`asyncio.Event`) para interrumpir la generación.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)


# ─── Eventos del canal de chat ─────────────────────────────────────────

class ChatEvent:
    """Evento publicado en un canal de chat.

    Attributes:
        event: Nombre del evento (token_chunk, generation_completed, etc.).
        data: Payload del evento (dict).
    """

    def __init__(self, event: str, data: dict[str, Any]) -> None:
        self.event = event
        self.data = data

    def to_json(self) -> str:
        return json.dumps({"event": self.event, "data": self.data}, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"ChatEvent({self.event}, {self.data})"


# ─── Pub/Sub ───────────────────────────────────────────────────────────

class ChatPubSub:
    """Pub/Sub en memoria para canales de chat.

    Es un singleton a nivel de proceso. Cada sesión de chat tiene un canal
    identificado por ``chat.<session_id>``.

    Uso típico:
        pubsub = ChatPubSub()
        queue = pubsub.subscribe("chat_0044")
        pubsub.publish("chat_0044", ChatEvent("token_chunk", {...}))
        event = await queue.get()
        pubsub.unsubscribe("chat_0044", queue)
    """

    _instance: ChatPubSub | None = None

    def __new__(cls) -> ChatPubSub:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queues: dict[str, list[asyncio.Queue[ChatEvent]]] = {}
            cls._instance._cancel_events: dict[str, asyncio.Event] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    # ------------------------------------------------------------------
    # Gestión de suscripciones
    # ------------------------------------------------------------------

    async def subscribe(self, session_id: str) -> asyncio.Queue[ChatEvent]:
        """Suscribe un consumidor al canal de una sesión.

        Returns:
            Una cola asyncio desde la que el consumidor leerá los eventos.
        """
        channel = self._channel_name(session_id)
        async with self._lock:
            if channel not in self._queues:
                self._queues[channel] = []
            queue: asyncio.Queue[ChatEvent] = asyncio.Queue()
            self._queues[channel].append(queue)
            # Asegurar que existe una señal de cancelación
            if session_id not in self._cancel_events:
                self._cancel_events[session_id] = asyncio.Event()
            _logger.debug("Suscriptor añadido al canal %s (total: %d)", channel, len(self._queues[channel]))
            return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[ChatEvent]) -> None:
        """Elimina un suscriptor del canal de una sesión."""
        channel = self._channel_name(session_id)
        async with self._lock:
            if channel in self._queues:
                try:
                    self._queues[channel].remove(queue)
                    _logger.debug("Suscriptor eliminado del canal %s", channel)
                except ValueError:
                    pass
                if not self._queues[channel]:
                    del self._queues[channel]
                    # Limpiar señal de cancelación si ya no hay suscriptores
                    self._cancel_events.pop(session_id, None)

    async def unsubscribe_all(self, session_id: str) -> None:
        """Elimina todos los suscriptores del canal de una sesión."""
        channel = self._channel_name(session_id)
        async with self._lock:
            self._queues.pop(channel, None)
            self._cancel_events.pop(session_id, None)
            _logger.debug("Todos los suscriptores eliminados del canal %s", channel)

    # ------------------------------------------------------------------
    # Publicación
    # ------------------------------------------------------------------

    async def publish(self, session_id: str, event: ChatEvent) -> int:
        """Publica un evento en el canal de una sesión.

        Args:
            session_id: ID de la sesión destino.
            event: Evento a publicar.

        Returns:
            Número de suscriptores que recibieron el evento.
        """
        channel = self._channel_name(session_id)
        async with self._lock:
            queues = list(self._queues.get(channel, []))
        delivered = 0
        for queue in queues:
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                _logger.warning("Cola llena en canal %s — evento descartado", channel)
        return delivered

    # ------------------------------------------------------------------
    # Señal de cancelación
    # ------------------------------------------------------------------

    def get_cancel_event(self, session_id: str) -> asyncio.Event:
        """Obtiene (o crea) la señal de cancelación para una sesión."""
        if session_id not in self._cancel_events:
            self._cancel_events[session_id] = asyncio.Event()
        return self._cancel_events[session_id]

    async def request_cancel(self, session_id: str) -> None:
        """Dispara la señal de cancelación para una sesión."""
        event = self.get_cancel_event(session_id)
        event.set()
        _logger.info("Cancelación solicitada para sesión %s", session_id)

    async def reset_cancel(self, session_id: str) -> None:
        """Resetea la señal de cancelación (para un nuevo turno)."""
        event = self.get_cancel_event(session_id)
        event.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _channel_name(session_id: str) -> str:
        return f"chat.{session_id}"