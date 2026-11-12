"""
services/brasaland_api/agent/tracing.py — Trace local y consultable de cada corrida.

Cada corrida se guarda como un documento TinyDB identificado por `run_id`, con
la pregunta, la respuesta final, el estado y la lista ordenada de pasos
(nodos y decisiones de aristas) con su entrada, salida, duración y error.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Literal, TypeVar

from tinydb import Query, TinyDB

from services.brasaland_api.agent.state import SupportAgentState

AGENT_DATA_DIR = Path(__file__).resolve().parent / "data"
TRACES_DB_FILE = Path(os.getenv("AGENT_TRACES_DB", str(AGENT_DATA_DIR / "traces.json")))

RunStatus = Literal["completed", "rejected", "error"]

_lock = threading.Lock()
_T = TypeVar("_T")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db() -> TinyDB:
    TRACES_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(TRACES_DB_FILE, indent=2, ensure_ascii=False)


def _summarize_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: document.get(key)
        for key in ("source_document", "section", "chunk_index", "score")
    }


def _summarize(value: Any) -> Any:
    """Reduce los chunks a sus metadatos para que el trace no crezca sin control."""
    if isinstance(value, dict):
        return {
            key: (
                [_summarize_document(doc) for doc in item]
                if key == "documents" and isinstance(item, list)
                else item
            )
            for key, item in value.items()
        }
    return value


def start_run(run_id: str, question: str) -> None:
    with _lock, _get_db() as db:
        db.insert(
            {
                "run_id": run_id,
                "question": question,
                "status": "running",
                "started_at": _utc_now(),
                "finished_at": None,
                "answer": None,
                "error": None,
                "usage_summary": None,
                "steps": [],
            }
        )


def finish_run(
    run_id: str,
    *,
    status: RunStatus,
    answer: str | None = None,
    error: str | None = None,
    usage_summary: list[str] | None = None,
) -> None:
    update: dict[str, Any] = {"status": status, "finished_at": _utc_now(), "answer": answer, "error": error}
    if usage_summary:
        update["usage_summary"] = usage_summary
    with _lock, _get_db() as db:
        db.update(update, Query().run_id == run_id)


def _append_step(run_id: str, step: dict[str, Any]) -> None:
    with _lock, _get_db() as db:
        trace_query = Query().run_id == run_id
        record = db.get(trace_query)
        if record is None or isinstance(record, list):
            return
        db.update({"steps": [*record["steps"], step]}, trace_query)


def get_trace(run_id: str) -> dict[str, Any] | None:
    with _lock, _get_db() as db:
        record = db.get(Query().run_id == run_id)
    if record is None or isinstance(record, list):
        return None
    return dict(record)


def _traced(
    kind: str, name: str, func: Callable[[SupportAgentState], _T]
) -> Callable[[SupportAgentState], _T]:
    @wraps(func)
    def wrapper(state: SupportAgentState) -> _T:
        started = time.perf_counter()
        step: dict[str, Any] = {
            "kind": kind,
            "name": name,
            "started_at": _utc_now(),
            "input": _summarize(dict(state)),
        }
        try:
            output = func(state)
        except Exception as exc:
            step.update(
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                output=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            _append_step(state["run_id"], step)
            raise
        step.update(
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            output=_summarize(output),
            error=None,
        )
        _append_step(state["run_id"], step)
        return output

    return wrapper


def traced_node(
    name: str, func: Callable[[SupportAgentState], _T]
) -> Callable[[SupportAgentState], _T]:
    return _traced("node", name, func)


def traced_edge(
    name: str, func: Callable[[SupportAgentState], _T]
) -> Callable[[SupportAgentState], _T]:
    return _traced("edge", name, func)
