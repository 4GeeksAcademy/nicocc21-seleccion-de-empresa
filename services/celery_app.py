"""Aplicación Celery de Brasaland (DEV-55).

Redis actúa como broker y backend de resultados. Los workers corren como
procesos separados: ``celery -A services.celery_app worker``.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from celery import Celery, Task, signals
from sqlalchemy import insert

from data.pipelines.storage import dead_letter_entries, get_engine

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_ATTEMPTS = 3
TASK_SOFT_TIME_LIMIT = 240
TASK_TIME_LIMIT = 300

_logger = logging.getLogger(__name__)


def send_to_dlq(
    task_id: str, task_name: str, attempt: int, error: str, args: Any, kwargs: Any
) -> None:
    """Registra una tarea fallida en la tabla dead_letter_entries (PostgreSQL)."""
    _logger.error(
        "DLQ: task_id=%s task_name=%s attempt=%d/%d error=%s",
        task_id, task_name, attempt, MAX_ATTEMPTS, error,
    )
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            insert(dead_letter_entries).values(
                task_id=task_id,
                task_name=task_name,
                attempt=attempt,
                error=error,
                failed_at=datetime.now(timezone.utc),
            )
        )


class DeadLetterTask(Task):
    """Task base con reintentos y DLQ."""

    abstract = True

    def on_retry(self, exc, task_id, args, kwargs, einfo):  # noqa: ANN001
        _logger.warning(
            "Tarea %s falló (task_id=%s, intento=%d/%d): %s",
            self.name, task_id, self.request.retries + 1, MAX_ATTEMPTS, exc,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):  # noqa: ANN001
        attempt = self.request.retries + 1
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


@signals.task_prerun.connect
def _log_task_start(task_id: str, task: Task, **kwargs: Any) -> None:  # noqa: ANN401
    _logger.info("TASK_START task_id=%s task=%s", task_id, task.name)


@signals.task_postrun.connect
def _log_task_end(
    task_id: str, task: Task, state: str, retval: Any, **kwargs: Any  # noqa: ANN401
) -> None:
    _logger.info("TASK_END task_id=%s task=%s state=%s", task_id, task.name, state)


@signals.task_failure.connect
def _log_task_failure(
    task_id: str, task: Task, args: tuple, kwargs: dict,  # noqa: ARG001
    exception: BaseException, einfo: Any, **extras: Any,  # noqa: ANN401, ARG001
) -> None:
    _logger.error(
        "TASK_FAILURE task_id=%s task=%s error=%s", task_id, task.name, exception,
    )
