"""
tests/test_notification_manager.py — Tests unitarios del NotificationManager.

Cubre:
  - Publicación y suscripción básica
  - Múltiples suscriptores en un canal
  - Historial circular (replay en reconexión)
  - Límite de historial
  - Estadísticas de suscriptores
"""

from __future__ import annotations

from services.brasaland_api.notifications import NotificationManager


def test_publish_and_receive() -> None:
    """Un suscriptor recibe el evento publicado."""
    mgr = NotificationManager()
    q = mgr.subscribe("rfp")

    event_id = mgr.publish("rfp", "rfp_ticket_created", {"ticket_id": "tkt_0001"})
    assert event_id >= 1

    received = q.get(timeout=1)
    assert received["id"] == event_id
    assert received["event"] == "rfp_ticket_created"
    assert received["data"]["ticket_id"] == "tkt_0001"


def test_multiple_subscribers() -> None:
    """Dos suscriptores reciben el mismo evento."""
    mgr = NotificationManager()
    q1 = mgr.subscribe("rfp")
    q2 = mgr.subscribe("rfp")

    mgr.publish("rfp", "test_event", {"msg": "hello"})

    r1 = q1.get(timeout=1)
    r2 = q2.get(timeout=1)
    assert r1["id"] == r2["id"]
    assert r1["event"] == r2["event"] == "test_event"


def test_different_channels() -> None:
    """Los eventos de un canal no llegan a suscriptores de otro."""
    mgr = NotificationManager()
    q_rfp = mgr.subscribe("rfp")
    q_sales = mgr.subscribe("sales")

    mgr.publish("rfp", "rfp_ticket_created", {"ticket_id": "tkt_0001"})

    # El suscriptor de rfp recibe el evento
    assert q_rfp.get(timeout=1) is not None
    # El suscriptor de sales no recibe nada (timeout rápido)
    import queue
    try:
        q_sales.get(timeout=0.5)
        assert False, "No debería recibir evento en otro canal"
    except queue.Empty:
        pass


def test_unsubscribe() -> None:
    """Un suscriptor dado de baja no recibe más eventos."""
    mgr = NotificationManager()
    q = mgr.subscribe("rfp")

    mgr.publish("rfp", "event_1", {})
    assert q.get(timeout=1) is not None

    mgr.unsubscribe("rfp", q)
    mgr.publish("rfp", "event_2", {})

    import queue
    try:
        q.get(timeout=0.5)
        assert False, "Suscriptor dado de baja no debería recibir eventos"
    except queue.Empty:
        pass


def test_history_replay() -> None:
    """El histórico permite replay de eventos perdidos."""
    mgr = NotificationManager()

    ids: list[int] = []
    for i in range(3):
        eid = mgr.publish("rfp", "test_event", {"seq": i})
        ids.append(eid)

    # Replay desde el ID del primer evento (exclusivo) = últimos 2 eventos
    replay = mgr.replay_from("rfp", ids[0])
    assert len(replay) == 2
    assert [ev["data"]["seq"] for ev in replay] == [1, 2]


def test_history_circular_buffer() -> None:
    """El histórico no excede MAX_HISTORY_PER_CHANNEL."""
    mgr = NotificationManager()
    from services.brasaland_api.notifications import MAX_HISTORY_PER_CHANNEL

    # Publicar más eventos del límite
    for i in range(MAX_HISTORY_PER_CHANNEL + 10):
        mgr.publish("rfp", "test_event", {"seq": i})

    replay = mgr.replay_from("rfp", 0)
    assert len(replay) <= MAX_HISTORY_PER_CHANNEL
    # Debe contener los eventos más recientes
    assert replay[0]["data"]["seq"] == (MAX_HISTORY_PER_CHANNEL + 10) - MAX_HISTORY_PER_CHANNEL


def test_subscriber_count() -> None:
    """Las estadísticas de suscriptores son correctas."""
    mgr = NotificationManager()
    assert mgr.subscriber_count == {}

    q1 = mgr.subscribe("rfp")
    q2 = mgr.subscribe("rfp")
    mgr.subscribe("sales")

    counts = mgr.subscriber_count
    assert counts["rfp"] == 2
    assert counts["sales"] == 1

    mgr.unsubscribe("rfp", q1)
    assert mgr.subscriber_count["rfp"] == 1

    mgr.unsubscribe("rfp", q2)
    assert mgr.subscriber_count["rfp"] == 0


def test_event_id_monotonic() -> None:
    """Los IDs de evento son monótonos crecientes."""
    mgr = NotificationManager()
    ids = [mgr.publish("rfp", "e", {"i": i}) for i in range(10)]
    for i in range(1, len(ids)):
        assert ids[i] > ids[i - 1]


def test_publish_from_sync_context() -> None:
    """Se puede publicar desde un hilo síncrono (threading)."""
    import threading
    import queue as qmod

    mgr = NotificationManager()
    q = mgr.subscribe("rfp")
    results: list[int] = []

    def publisher():
        eid = mgr.publish("rfp", "sync_event", {"from": "thread"})
        results.append(eid)

    t = threading.Thread(target=publisher)
    t.start()
    t.join(timeout=2)

    assert len(results) == 1
    received = q.get(timeout=1)
    assert received["id"] == results[0]
    assert received["event"] == "sync_event"