"""Persistencia y control de concurrencia de ejecuciones nocturnas."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from services.brasaland_api.database import engine
from services.telemetry.models import JobRun

JOB_NAME = "nightly_export"


def get_job_run(target_date: date, job_name: str = JOB_NAME) -> JobRun | None:
    with Session(engine) as session:
        return session.exec(
            select(JobRun).where(
                JobRun.job_name == job_name,
                JobRun.target_date == target_date,
            )
        ).first()


def create_job_run(target_date: date, job_name: str = JOB_NAME) -> JobRun:
    """Crea una fila ``pending`` o devuelve la existente para ese día."""
    with Session(engine) as session:
        existing = session.exec(
            select(JobRun).where(
                JobRun.job_name == job_name,
                JobRun.target_date == target_date,
            )
        ).first()
        if existing is not None:
            return existing

        run = JobRun(job_name=job_name, target_date=target_date, status="pending")
        session.add(run)
        try:
            session.commit()
            session.refresh(run)
            return run
        except IntegrityError:
            session.rollback()
            existing = session.exec(
                select(JobRun).where(
                    JobRun.job_name == job_name,
                    JobRun.target_date == target_date,
                )
            ).first()
            if existing is None:
                raise
            return existing


def has_processing_lock(job_name: str = JOB_NAME) -> bool:
    with Session(engine) as session:
        return (
            session.exec(
                select(JobRun.id).where(
                    JobRun.job_name == job_name,
                    JobRun.status == "processing",
                )
            ).first()
            is not None
        )


def has_completed_for_date(target_date: date, job_name: str = JOB_NAME) -> bool:
    with Session(engine) as session:
        return (
            session.exec(
                select(JobRun.id).where(
                    JobRun.job_name == job_name,
                    JobRun.target_date == target_date,
                    JobRun.status == "completed",
                )
            ).first()
            is not None
        )


def start_job_run(target_date: date, job_name: str = JOB_NAME) -> JobRun | None:
    """Cambia pending/failed a processing de forma atómica; ``None`` si hay lock."""
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        try:
            result = session.execute(
                update(JobRun)
                .where(
                    JobRun.job_name == job_name,
                    JobRun.target_date == target_date,
                    JobRun.status.in_(("pending", "failed")),
                )
                .values(
                    status="processing",
                    started_at=now,
                    finished_at=None,
                    error_message=None,
                )
            )
            if result.rowcount != 1:
                session.rollback()
                return None
            session.commit()
        except IntegrityError:
            session.rollback()
            return None

        return session.exec(
            select(JobRun).where(
                JobRun.job_name == job_name,
                JobRun.target_date == target_date,
            )
        ).first()


def update_job_run(
    target_date: date,
    status: str,
    error_message: str | None = None,
    job_name: str = JOB_NAME,
) -> None:
    if status not in {"completed", "failed"}:
        raise ValueError(f"Estado final no permitido: {status}")

    with Session(engine) as session:
        result = session.execute(
            update(JobRun)
            .where(
                JobRun.job_name == job_name,
                JobRun.target_date == target_date,
                JobRun.status == "processing",
            )
            .values(
                status=status,
                finished_at=datetime.now(timezone.utc),
                error_message=error_message,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            raise RuntimeError(f"No se encontró job processing para {target_date}")
        session.commit()


def fail_pending_job(
    target_date: date,
    error_message: str,
    job_name: str = JOB_NAME,
) -> None:
    """Registra como fallida una fila pending que no pudo adquirir el lock."""
    with Session(engine) as session:
        session.execute(
            update(JobRun)
            .where(
                JobRun.job_name == job_name,
                JobRun.target_date == target_date,
                JobRun.status == "pending",
            )
            .values(
                status="failed",
                finished_at=datetime.now(timezone.utc),
                error_message=error_message,
            )
        )
        session.commit()