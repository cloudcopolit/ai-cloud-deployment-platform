import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Ensure root path is in sys.path so ai package is importable
ROOT_DIR = Path(__file__).resolve().parents[4]
if not (ROOT_DIR / "ai").is_dir():
    ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai.agents.code_analyzer.analyzer import run_code_analyzer
from app.core.errors import NotFound
from app.core.permissions import check_team_role
from app.models import Branch, Commit, Project, Repository, RepositoryAnalysis, Service, User
from app.modules.analysis.schemas import AnalysisCreate, AnalysisJobRead


def _to_analysis_read(
    db: Session, analysis: RepositoryAnalysis, commit_sha: str | None = None
) -> AnalysisJobRead:
    if not commit_sha:
        commit = db.get(Commit, analysis.commit_id)
        commit_sha = commit.sha if commit else "unknown"

    service_count = (
        db.scalar(
            select(func.count()).select_from(Service).where(Service.analysis_id == analysis.id)
        )
        or 0
    )

    return AnalysisJobRead(
        id=analysis.id,
        repository_id=analysis.repository_id,
        commit_id=analysis.commit_id,
        commit_sha=commit_sha,
        status=analysis.status,
        created_at=analysis.created_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        requested_by=analysis.requested_by,
        error_code=analysis.error_code,
        error_message=analysis.error_message,
        services_count=service_count,
        report=analysis.analysis_data,
    )


def create_analysis_job(
    db: Session, repo_id: UUID, user: User, data: AnalysisCreate
) -> AnalysisJobRead:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")

    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    # Resolve commit
    commit = None
    if data.commit_sha:
        commit = db.scalar(
            select(Commit).where(Commit.repository_id == repo_id, Commit.sha == data.commit_sha)
        )

    if not commit:
        # Default: latest commit on deployment branch
        dep_branch_id = db.scalar(
            select(Branch.id).where(
                Branch.repository_id == repo_id,
                Branch.is_deployment_branch.is_(True),
            )
        )
        if dep_branch_id:
            commit = db.scalar(
                select(Commit)
                .where(Commit.repository_id == repo_id, Commit.branch_id == dep_branch_id)
                .order_by(Commit.committed_at.desc())
            )

    if not commit:
        # Fallback to any commit
        commit = db.scalar(
            select(Commit)
            .where(Commit.repository_id == repo_id)
            .order_by(Commit.committed_at.desc())
        )

    if not commit:
        raise NotFound("No commits found for repository to analyze.")

    now = datetime.now(UTC)
    analysis = RepositoryAnalysis(
        repository_id=repo.id,
        commit_id=commit.id,
        status="RUNNING",
        started_at=now,
        requested_by=user.id,
        report_schema_version="1.0",
    )
    db.add(analysis)
    db.flush()

    # Run deterministic Analysis Agent
    branch_name = db.scalar(select(Branch.name).where(Branch.id == commit.branch_id)) or "main"
    report = run_code_analyzer(
        owner=repo.owner,
        name=repo.name,
        branch=branch_name,
        commit_sha=commit.sha,
    )

    # Persist detected services
    for s in report.services:
        db_service = Service(
            analysis_id=analysis.id,
            name=s.name,
            service_type=s.service_type.value,
            language=s.language,
            framework=s.framework,
            path=s.path,
            port=s.port,
            metadata_=s.metadata,
        )
        db.add(db_service)

    analysis.status = "SUCCESS"
    analysis.completed_at = datetime.now(UTC)
    analysis.analysis_data = report.model_dump(mode="json")

    db.commit()
    db.refresh(analysis)

    return _to_analysis_read(db, analysis, commit.sha)


def get_analysis_details(db: Session, analysis_id: UUID, user: User) -> AnalysisJobRead:
    analysis = db.get(RepositoryAnalysis, analysis_id)
    if not analysis:
        raise NotFound("Analysis job not found.")

    repo = db.get(Repository, analysis.repository_id)
    if not repo:
        raise NotFound("Repository not found.")

    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")
    return _to_analysis_read(db, analysis)


def list_repository_analyses(db: Session, repo_id: UUID, user: User) -> list[AnalysisJobRead]:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")

    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    analyses = db.scalars(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id == repo_id)
        .order_by(RepositoryAnalysis.created_at.desc())
    ).all()

    return [_to_analysis_read(db, a) for a in analyses]


def list_project_analyses(db: Session, project_id: UUID, user: User) -> list[AnalysisJobRead]:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "MEMBER")

    repo_ids = select(Repository.id).where(Repository.project_id == project_id)
    analyses = db.scalars(
        select(RepositoryAnalysis)
        .where(RepositoryAnalysis.repository_id.in_(repo_ids))
        .order_by(RepositoryAnalysis.created_at.desc())
    ).all()

    return [_to_analysis_read(db, a) for a in analyses]
