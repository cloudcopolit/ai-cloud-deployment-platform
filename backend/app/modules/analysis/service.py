"""Analysis jobs (B3.5): created QUEUED and run by the worker, never inside the request."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound, RateLimited
from app.core.permissions import get_project_for_user, get_repository_for_user
from app.integrations.github_app import GitHubClient
from app.models import (
    AgentRun,
    AgentTask,
    Commit,
    Project,
    Repository,
    RepositoryAnalysis,
    Service,
    User,
)
from app.modules.analysis.schemas import (
    TERMINAL_STATUSES,
    ActivityRead,
    AgentRunRead,
    AgentTaskRead,
    AnalysisCreate,
    AnalysisJobRead,
    AnswersCreate,
)
from app.modules.repositories.service import resolve_commit

ACTIVE = ("QUEUED", "RUNNING")


def _ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return int((end - start).total_seconds() * 1000)


def _to_read(db: Session, job: RepositoryAnalysis, project_id: UUID) -> AnalysisJobRead:
    commit = db.get(Commit, job.commit_id)
    services = db.scalar(
        select(func.count()).select_from(Service).where(Service.analysis_id == job.id)
    )
    return AnalysisJobRead(
        id=job.id,
        repository_id=job.repository_id,
        project_id=project_id,
        commit_id=job.commit_id,
        commit_sha=commit.sha if commit else "",
        branch_name=job.branch_name,
        status=job.status,
        terminal=job.status in TERMINAL_STATUSES,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=_ms(job.started_at, job.completed_at),
        requested_by=job.requested_by,
        attempts=job.attempts,
        cancel_requested=job.cancel_requested,
        parent_analysis_id=job.parent_analysis_id,
        user_answers=job.user_answers or {},
        error_code=job.error_code,
        error_message=job.error_message,
        warnings=job.warnings or [],
        services_count=services or 0,
        report=job.analysis_data,
    )


def _job_for_user(
    db: Session, analysis_id: UUID, user: User
) -> tuple[RepositoryAnalysis, Repository, Project]:
    job = db.get(RepositoryAnalysis, analysis_id)
    if job is None:
        raise NotFound("Analysis not found.")
    repo, project = get_repository_for_user(db, user, job.repository_id)
    return job, repo, project


def _enforce_capacity(db: Session, team_id: UUID) -> None:
    active = db.scalar(
        select(func.count())
        .select_from(RepositoryAnalysis)
        .join(Repository, Repository.id == RepositoryAnalysis.repository_id)
        .join(Project, Project.id == Repository.project_id)
        .where(Project.team_id == team_id, RepositoryAnalysis.status.in_(ACTIVE))
    )
    if (active or 0) >= settings.max_active_jobs_per_team:
        raise RateLimited(
            f"Your team already has {active} analyses queued or running. Wait for one to finish.",
            details={"limit": settings.max_active_jobs_per_team},
        )


def create_analysis_job(
    db: Session,
    github: GitHubClient,
    repo_id: UUID,
    user: User,
    data: AnalysisCreate,
    idempotency_key: str | None = None,
) -> AnalysisJobRead:
    repo, project = get_repository_for_user(db, user, repo_id)
    if idempotency_key:
        existing = db.scalar(
            select(RepositoryAnalysis).where(
                RepositoryAnalysis.requested_by == user.id,
                RepositoryAnalysis.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.repository_id != repo.id:
                raise Conflict("This Idempotency-Key was already used for another repository.")
            return _to_read(db, existing, project.id)
    if project.status != "ACTIVE":
        raise Conflict("The project is archived; it accepts no new work.")
    _enforce_capacity(db, project.team_id)
    commit = resolve_commit(db, github, repo, data.branch, data.commit_sha)
    job = RepositoryAnalysis(
        repository_id=repo.id,
        commit_id=commit.id,
        status="QUEUED",
        requested_by=user.id,
        branch_name=data.branch or None,
        idempotency_key=idempotency_key,
        user_answers={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_read(db, job, project.id)


def answer_and_rerun(
    db: Session, analysis_id: UUID, user: User, data: AnswersCreate
) -> AnalysisJobRead:
    parent, repo, project = _job_for_user(db, analysis_id, user)
    if parent.status != "BLOCKED":
        raise Conflict("Only a BLOCKED analysis can be answered.")
    asked = {m.get("key") for m in (parent.analysis_data or {}).get("missing_info", [])}
    unknown = sorted(set(data.answers) - asked)
    if unknown:
        raise BadRequest("These answers match no open question.", details={"keys": unknown})
    if project.status != "ACTIVE":
        raise Conflict("The project is archived; it accepts no new work.")
    _enforce_capacity(db, project.team_id)
    job = RepositoryAnalysis(
        repository_id=repo.id,
        commit_id=parent.commit_id,
        status="QUEUED",
        requested_by=user.id,
        branch_name=parent.branch_name,
        parent_analysis_id=parent.id,
        user_answers={**(parent.user_answers or {}), **data.answers},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_read(db, job, project.id)


def cancel_analysis(db: Session, analysis_id: UUID, user: User) -> AnalysisJobRead:
    job, _, project = _job_for_user(db, analysis_id, user)
    locked = db.scalar(
        select(RepositoryAnalysis).where(RepositoryAnalysis.id == job.id).with_for_update()
    )
    if locked is None:  # pragma: no cover - loaded above
        raise NotFound("Analysis not found.")
    if locked.status in TERMINAL_STATUSES:
        raise Conflict(f"The analysis already finished ({locked.status}).")
    if locked.status == "QUEUED":
        locked.status = "CANCELLED"
        locked.error_code = "JOB_CANCELLED"
        locked.error_message = "Cancelled before it started."
        locked.completed_at = func.now()
    locked.cancel_requested = True  # a RUNNING job stops at the worker's next heartbeat
    db.commit()
    db.refresh(locked)
    return _to_read(db, locked, project.id)


def get_analysis_details(db: Session, analysis_id: UUID, user: User) -> AnalysisJobRead:
    job, _, project = _job_for_user(db, analysis_id, user)
    return _to_read(db, job, project.id)


def get_activity(db: Session, analysis_id: UUID, user: User) -> ActivityRead:
    job, _, _ = _job_for_user(db, analysis_id, user)
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.analysis_id == job.id)
        # started_at is set per event in Python; created_at is the transaction's now()
        .order_by(AgentRun.started_at.nulls_last(), AgentRun.created_at, AgentRun.id)
    ).all()
    tasks = db.scalars(
        select(AgentTask)
        .where(AgentTask.agent_run_id.in_([r.id for r in runs]))
        .order_by(AgentTask.step_order)
    ).all()
    by_run: dict[UUID, list[AgentTaskRead]] = {}
    for t in tasks:
        by_run.setdefault(t.agent_run_id, []).append(
            AgentTaskRead(
                id=t.id,
                task_type=t.task_type,
                status=t.status,
                step_order=t.step_order,
                started_at=t.started_at,
                completed_at=t.completed_at,
                duration_ms=_ms(t.started_at, t.completed_at),
                output=t.output_data,
                error_code=t.error_code,
                error_message=t.error_message,
            )
        )
    return ActivityRead(
        analysis_id=job.id,
        status=job.status,
        terminal=job.status in TERMINAL_STATUSES,
        attempts=job.attempts,
        cancel_requested=job.cancel_requested,
        heartbeat_at=job.heartbeat_at,
        runs=[
            AgentRunRead(
                id=r.id,
                agent_type=r.agent_type,
                status=r.status,
                model=r.model,
                usage=r.usage,
                started_at=r.started_at,
                completed_at=r.completed_at,
                duration_ms=_ms(r.started_at, r.completed_at),
                input=r.input_data,
                output=r.output_data,
                error_code=r.error_code,
                error_message=r.error_message,
                tasks=by_run.get(r.id, []),
            )
            for r in runs
        ],
    )


def list_services(db: Session, analysis_id: UUID, user: User) -> list[dict]:
    job, _, _ = _job_for_user(db, analysis_id, user)
    rows = db.scalars(
        select(Service).where(Service.analysis_id == job.id).order_by(Service.name)
    ).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "service_type": s.service_type,
            "language": s.language,
            "framework": s.framework,
            "path": s.path,
            "port": s.port,
            "metadata": s.metadata_,
        }
        for s in rows
    ]


def list_repository_analyses(
    db: Session, repo_id: UUID, user: User, limit: int = 20, offset: int = 0
) -> list[AnalysisJobRead]:
    repo, project = get_repository_for_user(db, user, repo_id)
    jobs = db.scalars(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id == repo.id)
        .order_by(RepositoryAnalysis.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_to_read(db, j, project.id) for j in jobs]


def list_project_analyses(
    db: Session, project_id: UUID, user: User, limit: int = 20, offset: int = 0
) -> list[AnalysisJobRead]:
    project = get_project_for_user(db, user, project_id)
    repo_ids = select(Repository.id).where(Repository.project_id == project.id)
    jobs = db.scalars(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id.in_(repo_ids))
        .order_by(RepositoryAnalysis.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_to_read(db, j, project.id) for j in jobs]
