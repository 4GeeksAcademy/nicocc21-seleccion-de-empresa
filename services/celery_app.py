"""Aplicación Celery de Brasaland (DEV-55).

Redis actúa como broker y backend de resultados. Los workers corren como
procesos separados: ``celery -A services.celery_app worker``.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis
from celery import Celery, Task

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_ATTEMPTS = 3
DLQ_KEY = "dead_letter"
TASK_SOFT_TIME_LIMIT = 240
TASK_TIME_LIMIT = 300

_logger = logging.getLogger(__name__)


def send_to_dlq(
    task_id: str, task_name: str, attempt: int, error: str, args: Any, kwargs: Any
) -> None:
    entry = {
        "task_id": task_id,
        "task_name": task_name,
        "attempt": attempt,
        "error": error,
        "args": args,
        "kwargs": kwargs,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    redis.Redis.from_url(REDIS_URL).rpush(DLQ_KEY, json.dumps(entry, default=str))


class DeadLetterTask(Task):
    """Registra cada reintento y envía a la DLQ cuando se agotan los intentos."""

    def on_retry(self, exc, task_id, args, kwargs, einfo):  # noqa: ANN001
        _logger.warning(
            "Tarea %s falló (task_id=%s, intento=%d/%d): %s",
            self.name, task_id, self.request.retries + 1, MAX_ATTEMPTS, exc,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: ANN001
        attempt = self.request.retries + 1
        _logger.error(
            "Tarea %s a DLQ (task_id=%s, intento=%d/%d): %s",
            self.name, task_id, attempt, MAX_ATTEMPTS, exc,
        )
        send_to_dlq(task_id, self.name, attempt, str(exc), args, kwargs)


celery_app = Celery(
    "brasaland",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.reporting.tasks"],
    task_cls=DeadLetterTask,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    task_time_limit=TASK_TIME_LIMIT,
    result_expires=86400,
    timezone="UTC",
)
