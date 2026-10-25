"""Execute one claimed analysis job: build the request, heartbeat while the orchestrator runs,
then persist the terminal state."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable

from cloudpilot_ai import analyze_repository, run_analysis
from cloudpilot_ai.contracts import AnalysisRequest, RepositoryRef
from cloudpilot_ai.orchestrator import Policies
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.github_app import GitHubClient
from app.jobs.gateway import GitHubRepositoryGateway
from app.jobs.queue import Finish, finish, heartbeat
from app.jobs.sink import DbEventSink
from app.models import Commit, Project, Repository, RepositoryAnalysis

logger = logging.getLogger("cloudpilot.worker")


class _Flag:
    def __init__(self, event: threading.Event) -> None:
        self._event = event

    def is_cancelled(self) -> bool:
        return self._event.is_set()


def _build_request(
    db: Session, job: RepositoryAnalysis
) -> tuple[AnalysisRequest, Repository, Project]:
    repo = db.get(Repository, job.repository_id)
    commit = db.get(Commit, job.commit_id)
    if repo is None or commit is None:
        raise LookupError("repository or commit vanished")
    project = db.get(Project, repo.project_id)
    if project is None:
        raise LookupError("project vanished")
    request = AnalysisRequest(
        job_id=job.id,
        correlation_id=f"analysis-{job.id}",
        repository=RepositoryRef(
            owner=repo.owner,
            name=repo.name,
            branch=(job.branch_name or repo.default_branch)[:255],
            commit_sha=commit.sha,
        ),
        github_installation_ref=f"repository:{repo.id}",  # opaque; resolved by the gateway
        user_answers={str(k): str(v) for k, v in (job.user_answers or {}).items()},
    )
    return request, repo, project


def execute(
    job_id: uuid.UUID,
    worker_id: str,
    *,
    session_factory: Callable[[], Session],
    github: GitHubClient,
    policies: Policies | None = None,
) -> str | None:
    """Run the job. Returns the terminal status, or None if the job was taken away from this
    worker (sweeper re-queued it) and the result was discarded."""
    with session_factory() as db:
        job = db.get(RepositoryAnalysis, job_id)
        if job is None:
            return None
        try:
            request, repo, project = _build_request(db, job)
        except (LookupError, ValueError) as exc:
            finish(
                db,
                job_id,
                worker_id,
                Finish(
                    "FAILED", "INTERNAL_ERROR", f"The job could not start: {type(exc).__name__}."
                ),
            )
            return "FAILED"

    cancel = threading.Event()
    lost = threading.Event()
    done = threading.Event()

    def beat() -> None:
        while not done.wait(settings.worker_heartbeat_interval_s):
            try:
                with session_factory() as hb:
                    ours, cancel_requested = heartbeat(hb, job_id, worker_id)
            except Exception:  # a missed beat is tolerated; the sweeper decides staleness
                logger.warning("heartbeat_failed", extra={"context": {"job_id": str(job_id)}})
                continue
            if not ours:
                lost.set()
                cancel.set()
            elif cancel_requested:
                cancel.set()

    beater = threading.Thread(target=beat, name=f"heartbeat-{job_id}", daemon=True)
    beater.start()
    try:
        outcome = run_analysis(
            request,
            repository=GitHubRepositoryGateway(
                github, owner=repo.owner, name=repo.name, sha=request.repository.commit_sha
            ),
            sink=DbEventSink(session_factory, analysis_id=job_id, project_id=project.id),
            analysis_agent=analyze_repository,
            cancel=_Flag(cancel),
            timeout_s=settings.job_timeout_s,
            policies=policies,
        )
    finally:
        done.set()
        beater.join(timeout=5)

    if lost.is_set():
        logger.warning("job_lost", extra={"context": {"job_id": str(job_id)}})
        return None
    error = outcome.error
    result = Finish(
        status=outcome.status.value,
        error_code=error.code.value if error else None,
        error_message=error.message if error else None,
        warnings=[w.model_dump(mode="json") for w in outcome.warnings],
    )
    with session_factory() as db:
        if not finish(db, job_id, worker_id, result):
            return None
    logger.info(
        "job_finished",
        extra={
            "context": {"job_id": str(job_id), "status": result.status, "error": result.error_code}
        },
    )
    return result.status
