"""Worker, queue and sweeper (10 §4 "worker / jobs"): exclusive claims, heartbeat, stale-job
recovery, cancel, timeouts, failures. These tests commit for real (row locks only exist across
connections) and truncate the _test database afterwards."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.jobs import queue
from app.jobs.runner import execute
from app.models import (
    AgentRun,
    AgentTask,
    Branch,
    Commit,
    Project,
    Repository,
    RepositoryAnalysis,
    Service,
    Team,
    User,
)
from tests.fakes import FakeGitHub

FASTAPI_REPO = {
    "requirements.txt": "fastapi==0.115.0\nuvicorn==0.32.0\npsycopg==3.2.3\n",
    "main.py": 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef h():\n'
    "    return {}\n",
    "Dockerfile": 'FROM python:3.12-slim\nEXPOSE 8000\nCMD ["uvicorn", "main:app"]\n',
}
SQLITE_REPO = {
    "requirements.txt": "flask==3.0.3\n",
    "app.py": "import sqlite3\nfrom flask import Flask\napp = Flask(__name__)\n"
    "sqlite3.connect('x.db')\n@app.route('/health')\ndef h():\n    return ''\n",
    "Dockerfile": "FROM python:3.12-slim\nEXPOSE 5000\n",
}

SessionFactory = Callable[[], Session]


@pytest.fixture
def committed(migrated_engine: Engine) -> Iterator[SessionFactory]:
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        with migrated_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def fast_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_heartbeat_interval_s", 0.05)
    monkeypatch.setattr(settings, "worker_stale_after_s", 5)


def _seed(
    factory: SessionFactory, fake: FakeGitHub, files: dict[str, str], *, jobs: int = 1
) -> list[uuid.UUID]:
    remote = fake.add_repo("acme", f"shop-{uuid.uuid4().hex[:6]}")
    sha = remote.add_commit("main", "init", files)
    with factory() as db:
        user = User(github_user_id=uuid.uuid4().hex[:12], name="Owner")
        team = Team(name="T")
        db.add_all([user, team])
        db.flush()
        project = Project(team_id=team.id, name="P", status="ACTIVE")
        db.add(project)
        db.flush()
        repo = Repository(
            project_id=project.id,
            github_repository_id=str(remote.github_id),
            owner=remote.owner,
            name=remote.name,
            url="https://github.com/x/y",
            default_branch="main",
        )
        db.add(repo)
        db.flush()
        branch = Branch(
            repository_id=repo.id, name="main", is_default=True, is_deployment_branch=True
        )
        db.add(branch)
        db.flush()
        commit = Commit(
            repository_id=repo.id,
            branch_id=branch.id,
            sha=sha,
            message="init",
            committed_at=datetime.now(UTC),
        )
        db.add(commit)
        db.flush()
        ids = []
        for _ in range(jobs):
            job = RepositoryAnalysis(
                repository_id=repo.id, commit_id=commit.id, status="QUEUED", requested_by=user.id
            )
            db.add(job)
            db.flush()
            ids.append(job.id)
        db.commit()
    return ids


def _job(factory: SessionFactory, job_id: uuid.UUID) -> RepositoryAnalysis:
    with factory() as db:
        job = db.get(RepositoryAnalysis, job_id)
        assert job is not None
        return job


def _claim_in_parallel(factory: SessionFactory, workers: int) -> list[uuid.UUID | None]:
    barrier = threading.Barrier(workers)
    results: list[uuid.UUID | None] = [None] * workers

    def worker(i: int) -> None:
        with factory() as db:
            barrier.wait()
            results[i] = queue.claim_next(db, f"w{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return results


def test_two_workers_never_claim_the_same_job(committed, fake_github) -> None:
    ids = _seed(committed, fake_github, FASTAPI_REPO, jobs=2)
    claimed = _claim_in_parallel(committed, 3)
    got = [c for c in claimed if c is not None]
    assert sorted(got) == sorted(ids)  # each job exactly once, the third worker got nothing
    assert claimed.count(None) == 1
    for job_id in ids:
        job = _job(committed, job_id)
        assert (job.status, job.attempts) == ("RUNNING", 1)
        assert job.locked_by is not None
        assert job.deadline_at is not None


def test_worker_runs_a_real_analysis_and_records_activity(
    committed, fake_github, fast_worker
) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    with committed() as db:
        assert queue.claim_next(db, "w1") == job_id

    status = execute(job_id, "w1", session_factory=committed, github=fake_github.client())

    assert status == "SUCCESS"
    job = _job(committed, job_id)
    assert (job.status, job.error_code, job.locked_by) == ("SUCCESS", None, None)
    assert job.analysis_data is not None
    assert job.analysis_data["services"][0]["framework"] == "FastAPI"
    with committed() as db:
        runs = db.scalars(select(AgentRun).where(AgentRun.analysis_id == job_id)).all()
        assert sorted((r.agent_type, r.status) for r in runs) == [
            ("ANALYSIS", "SUCCESS"),
            ("ORCHESTRATOR", "SUCCESS"),
        ]
        analysis_run = next(r for r in runs if r.agent_type == "ANALYSIS")
        tasks = db.scalars(
            select(AgentTask)
            .where(AgentTask.agent_run_id == analysis_run.id)
            .order_by(AgentTask.step_order)
        ).all()
        assert tasks[0].task_type == "read_repository"
        assert all(t.completed_at is not None for t in tasks)
        assert [
            s.port for s in db.scalars(select(Service).where(Service.analysis_id == job_id))
        ] == [8000]


def test_blocked_analysis_is_a_normal_outcome(committed, fake_github, fast_worker) -> None:
    (job_id,) = _seed(committed, fake_github, SQLITE_REPO)
    with committed() as db:
        queue.claim_next(db, "w1")
    assert (
        execute(job_id, "w1", session_factory=committed, github=fake_github.client()) == "BLOCKED"
    )
    job = _job(committed, job_id)
    assert job.error_code is None
    assert job.analysis_data is not None
    assert [m["key"] for m in job.analysis_data["missing_info"]] == ["datastore:sqlite"]


def test_repository_gone_fails_with_a_clear_code(committed, fake_github, fast_worker) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    fake_github.repos.clear()  # deleted (or made private) after it was connected
    with committed() as db:
        queue.claim_next(db, "w1")
    assert execute(job_id, "w1", session_factory=committed, github=fake_github.client()) == "FAILED"
    assert _job(committed, job_id).error_code == "REPOSITORY_NOT_FOUND"


def test_job_timeout(committed, fake_github, fast_worker, monkeypatch) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    fake_github.raw_delay = 2.5  # every file read is slower than the whole job may take
    monkeypatch.setattr(settings, "job_timeout_s", 1)
    with committed() as db:
        queue.claim_next(db, "w1")
    assert (
        execute(job_id, "w1", session_factory=committed, github=fake_github.client()) == "TIMED_OUT"
    )
    job = _job(committed, job_id)
    assert job.error_code in {"JOB_TIMEOUT", "STAGE_TIMEOUT"}


def test_cancel_while_running(committed, fake_github, fast_worker) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    fake_github.raw_delay = 0.4
    with committed() as db:
        queue.claim_next(db, "w1")
    result: list[str | None] = []
    runner = threading.Thread(
        target=lambda: result.append(
            execute(job_id, "w1", session_factory=committed, github=fake_github.client())
        )
    )
    runner.start()
    with committed() as db:
        db.get(RepositoryAnalysis, job_id).cancel_requested = True  # what POST /cancel does
        db.commit()
    runner.join(30)
    assert result == ["CANCELLED"]
    assert _job(committed, job_id).error_code == "JOB_CANCELLED"


def test_stale_job_is_requeued_then_timed_out(committed, fake_github, monkeypatch) -> None:
    monkeypatch.setattr(settings, "worker_stale_after_s", 5)
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    with committed() as db:
        queue.claim_next(db, "dead-worker")
        job = db.get(RepositoryAnalysis, job_id)
        job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        run = AgentRun(
            project_id=db.scalar(select(Project.id)),
            analysis_id=job_id,
            agent_type="ANALYSIS",
            status="RUNNING",
        )
        db.add(run)
        db.commit()

    with committed() as db:
        swept = queue.sweep(db)
    assert (swept.requeued, swept.timed_out) == (1, 0)
    job = _job(committed, job_id)
    assert (job.status, job.locked_by) == ("QUEUED", None)
    with committed() as db:  # the dead worker's run is closed truthfully, not left RUNNING
        assert db.scalar(select(AgentRun.status).where(AgentRun.analysis_id == job_id)) == "FAILED"

    with committed() as db:  # second attempt also dies
        queue.claim_next(db, "dead-again")
        db.get(RepositoryAnalysis, job_id).heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
        swept = queue.sweep(db)
    assert swept.timed_out == 1
    job = _job(committed, job_id)
    assert (job.status, job.error_code, job.attempts) == ("TIMED_OUT", "WORKER_LOST", 2)


def test_crashed_worker_job_completes_on_retry(
    committed, fake_github, fast_worker, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "worker_stale_after_s", 5)
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    with committed() as db:
        queue.claim_next(db, "crashed")
        db.get(RepositoryAnalysis, job_id).heartbeat_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        queue.sweep(db)
        assert queue.claim_next(db, "healthy") == job_id
    assert (
        execute(job_id, "healthy", session_factory=committed, github=fake_github.client())
        == "SUCCESS"
    )
    assert _job(committed, job_id).attempts == 2


def test_result_is_discarded_when_the_job_was_taken_away(
    committed, fake_github, fast_worker
) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    fake_github.raw_delay = 0.3
    with committed() as db:
        queue.claim_next(db, "slow")
    result: list[str | None] = []
    runner = threading.Thread(
        target=lambda: result.append(
            execute(job_id, "slow", session_factory=committed, github=fake_github.client())
        )
    )
    runner.start()
    with committed() as db:  # the sweeper re-queued it and another worker took it
        job = db.get(RepositoryAnalysis, job_id)
        job.locked_by = "other"
        db.commit()
    runner.join(30)
    assert result == [None]
    assert _job(committed, job_id).locked_by == "other"


def test_cancelled_queued_jobs_are_settled_by_the_sweeper(committed, fake_github) -> None:
    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    with committed() as db:
        db.get(RepositoryAnalysis, job_id).cancel_requested = True
        db.commit()
        assert queue.claim_next(db, "w") is None  # never claimed
        assert queue.sweep(db).cancelled == 1
    assert _job(committed, job_id).status == "CANCELLED"


def test_worker_loop_processes_one_job(committed, fake_github, fast_worker, monkeypatch) -> None:
    from app.jobs import worker

    (job_id,) = _seed(committed, fake_github, FASTAPI_REPO)
    monkeypatch.setattr(worker, "SessionLocal", committed)
    monkeypatch.setattr(worker, "get_github_client", fake_github.client)
    assert worker.run(threading.Event(), once=True) == 1
    assert _job(committed, job_id).status == "SUCCESS"
    assert worker.run(threading.Event(), once=True) == 0  # queue empty
