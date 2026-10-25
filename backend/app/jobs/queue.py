"""PostgreSQL as the job queue (ADR-008): claim with FOR UPDATE SKIP LOCKED, heartbeat while
running, and a sweeper that recovers jobs whose worker disappeared."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AgentRun, AgentTask, RepositoryAnalysis

TERMINAL = frozenset({"SUCCESS", "BLOCKED", "FAILED", "TIMED_OUT", "CANCELLED"})


def _now() -> datetime:
    return datetime.now(UTC)


def claim_next(db: Session, worker_id: str) -> uuid.UUID | None:
    """Atomically take the oldest QUEUED job. Two workers never get the same job: the row
    lock plus SKIP LOCKED makes the second worker skip it."""
    job = db.scalar(
        select(RepositoryAnalysis)
        .where(
            RepositoryAnalysis.status == "QUEUED", RepositoryAnalysis.cancel_requested.is_(False)
        )
        .order_by(RepositoryAnalysis.created_at, RepositoryAnalysis.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.rollback()
        return None
    now = _now()
    job.status = "RUNNING"
    job.locked_by = worker_id
    job.attempts = (job.attempts or 0) + 1
    job.started_at = now
    job.heartbeat_at = now
    job.deadline_at = now + timedelta(seconds=settings.job_timeout_s + 30)
    job.error_code = None
    job.error_message = None
    db.commit()
    return job.id


def heartbeat(db: Session, job_id: uuid.UUID, worker_id: str) -> tuple[bool, bool]:
    """Record liveness. Returns (still_ours, cancel_requested)."""
    row = db.execute(
        update(RepositoryAnalysis)
        .where(
            RepositoryAnalysis.id == job_id,
            RepositoryAnalysis.locked_by == worker_id,
            RepositoryAnalysis.status == "RUNNING",
        )
        .values(heartbeat_at=_now())
        .returning(RepositoryAnalysis.cancel_requested)
    ).first()
    db.commit()
    if row is None:
        return False, True
    return True, bool(row[0])


@dataclass
class Finish:
    status: str
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[dict] | None = None


def finish(db: Session, job_id: uuid.UUID, worker_id: str, result: Finish) -> bool:
    """Write the terminal state, but only if this worker still owns the job (a sweeper may have
    re-queued it). Returns False when the result was discarded."""
    job = db.scalar(
        select(RepositoryAnalysis).where(RepositoryAnalysis.id == job_id).with_for_update()
    )
    if job is None or job.locked_by != worker_id or job.status != "RUNNING":
        db.rollback()
        return False
    job.status = result.status
    job.completed_at = _now()
    job.error_code = result.error_code
    job.error_message = result.error_message
    job.warnings = result.warnings or []
    job.locked_by = None
    _close_open_runs(db, job.id, "CANCELLED" if result.status == "CANCELLED" else "FAILED")
    db.commit()
    return True


def _close_open_runs(
    db: Session, job_id: uuid.UUID, status: str, reason: str | None = None
) -> None:
    """Runs/tasks still RUNNING when a job ends can never finish; close them truthfully."""
    now = _now()
    runs = db.scalars(
        select(AgentRun).where(AgentRun.analysis_id == job_id, AgentRun.status == "RUNNING")
    ).all()
    for run in runs:
        run.status = status
        run.completed_at = now
        if reason:
            run.error_code = run.error_code or "WORKER_LOST"
            run.error_message = run.error_message or reason
        db.execute(
            update(AgentTask)
            .where(AgentTask.agent_run_id == run.id, AgentTask.status == "RUNNING")
            .values(status="FAILED", completed_at=now, error_message=reason or "Run ended.")
        )


@dataclass
class SweepResult:
    requeued: int = 0
    timed_out: int = 0
    cancelled: int = 0


def sweep(db: Session) -> SweepResult:
    """Recover stale RUNNING jobs (worker crashed or hung) and settle cancelled QUEUED ones."""
    now = _now()
    stale_before = now - timedelta(seconds=settings.worker_stale_after_s)
    result = SweepResult()
    stale = db.scalars(
        select(RepositoryAnalysis)
        .where(
            RepositoryAnalysis.status == "RUNNING",
            (RepositoryAnalysis.heartbeat_at < stale_before)
            | (RepositoryAnalysis.deadline_at < now),
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in stale:
        past_deadline = job.deadline_at is not None and job.deadline_at < now
        if job.cancel_requested:
            job.status, job.error_code = "CANCELLED", "JOB_CANCELLED"
            job.error_message = "Cancelled; the worker stopped responding before it confirmed."
            job.completed_at = now
            result.cancelled += 1
            _close_open_runs(db, job.id, "CANCELLED", "Worker stopped responding.")
        elif not past_deadline and (job.attempts or 0) < settings.job_max_attempts:
            job.status = "QUEUED"
            job.started_at = None
            result.requeued += 1
            _close_open_runs(db, job.id, "FAILED", "Worker stopped responding; job re-queued.")
        else:
            job.status = "TIMED_OUT"
            job.error_code = "JOB_TIMEOUT" if past_deadline else "WORKER_LOST"
            job.error_message = (
                "The job exceeded its time limit."
                if past_deadline
                else "The worker running this job stopped responding too many times."
            )
            job.completed_at = now
            result.timed_out += 1
            _close_open_runs(db, job.id, "TIMED_OUT", job.error_message)
        job.locked_by = None
    for job in db.scalars(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.status == "QUEUED", RepositoryAnalysis.cancel_requested.is_(True))
        .with_for_update(skip_locked=True)
    ):
        job.status, job.error_code, job.completed_at = "CANCELLED", "JOB_CANCELLED", now
        job.error_message = "Cancelled before it started."
        result.cancelled += 1
    db.commit()
    return result
