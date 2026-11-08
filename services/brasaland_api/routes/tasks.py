from __future__ import annotations

from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter

from services.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}")
def get_task_status(task_id: str) -> dict[str, Any]:
    result = AsyncResult(task_id, app=celery_app)
    state = result.state.lower()
    body: dict[str, Any] = {"task_id": task_id, "status": state}
    if state == "success":
        body["result"] = result.result
    elif state == "failure":
        body["error"] = str(result.result)
    return body
