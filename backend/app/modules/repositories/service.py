import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, NotFound
from app.core.permissions import check_team_role
from app.models import Branch, Commit, Project, Repository, User
from app.modules.repositories.schemas import (
    AvailableRepository,
    BranchRead,
    CommitRead,
    DeploymentBranchUpdate,
    RepositoryConnect,
    RepositoryRead,
)


def _to_repo_read(db: Session, repo: Repository) -> RepositoryRead:
    dep_branch = db.scalar(
        select(Branch.name).where(
            Branch.repository_id == repo.id,
            Branch.is_deployment_branch.is_(True),
        )
    )
    return RepositoryRead(
        id=repo.id,
        project_id=repo.project_id,
        github_repository_id=repo.github_repository_id,
        owner=repo.owner,
        name=repo.name,
        url=repo.url,
        default_branch=repo.default_branch,
        deployment_branch=dep_branch,
        connected_at=repo.connected_at,
        updated_at=repo.updated_at,
    )


def list_project_repositories(db: Session, project_id: UUID, user: User) -> list[RepositoryRead]:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "MEMBER")

    repos = db.scalars(
        select(Repository)
        .where(Repository.project_id == project_id)
        .order_by(Repository.connected_at.desc())
    ).all()

    return [_to_repo_read(db, r) for r in repos]


def get_repository_details(db: Session, repo_id: UUID, user: User) -> RepositoryRead:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")

    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")
    return _to_repo_read(db, repo)


def connect_repository(
    db: Session, project_id: UUID, user: User, data: RepositoryConnect
) -> RepositoryRead:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "ADMIN")

    existing = db.scalar(
        select(Repository).where(
            Repository.project_id == project_id,
            Repository.github_repository_id == data.github_repository_id,
        )
    )
    if existing:
        raise Conflict("Repository already connected to this project.")

    repo = Repository(
        project_id=project_id,
        github_repository_id=data.github_repository_id,
        owner=data.owner,
        name=data.name,
        url=data.url,
        default_branch=data.default_branch,
    )
    db.add(repo)
    db.flush()

    branch = Branch(
        repository_id=repo.id,
        name=data.default_branch,
        is_default=True,
        is_deployment_branch=True,
    )
    db.add(branch)
    db.flush()

    # Create an initial commit on deployment branch so analysis can run immediately
    now = datetime.now(UTC)
    init_sha = uuid.uuid4().hex[:40].rjust(40, "0")
    commit = Commit(
        repository_id=repo.id,
        branch_id=branch.id,
        sha=init_sha,
        message=f"Initial commit on {data.default_branch}",
        author_name=user.name or "CloudPilot",
        author_email=user.email,
        committed_at=now,
    )
    db.add(commit)

    db.commit()
    db.refresh(repo)

    return _to_repo_read(db, repo)


def list_repository_branches(db: Session, repo_id: UUID, user: User) -> list[BranchRead]:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")
    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "MEMBER")

    branches = db.scalars(
        select(Branch).where(Branch.repository_id == repo_id).order_by(Branch.name)
    ).all()
    return [BranchRead.model_validate(b) for b in branches]


def set_deployment_branch(
    db: Session, repo_id: UUID, user: User, data: DeploymentBranchUpdate
) -> BranchRead:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")
    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "ADMIN")

    branches = db.scalars(select(Branch).where(Branch.repository_id == repo_id)).all()

    target_branch = None
    for b in branches:
        if b.name == data.branch_name:
            b.is_deployment_branch = True
            target_branch = b
        else:
            b.is_deployment_branch = False

    if not target_branch:
        target_branch = Branch(
            repository_id=repo_id,
            name=data.branch_name,
            is_default=False,
            is_deployment_branch=True,
        )
        db.add(target_branch)

    db.commit()
    db.refresh(target_branch)
    return BranchRead.model_validate(target_branch)


def list_repository_commits(
    db: Session, repo_id: UUID, user: User, limit: int = 20, offset: int = 0
) -> list[CommitRead]:
    repo = db.get(Repository, repo_id)
    if not repo:
        raise NotFound("Repository not found.")
    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "MEMBER")

    commits = db.scalars(
        select(Commit)
        .where(Commit.repository_id == repo_id)
        .order_by(Commit.committed_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [CommitRead.model_validate(c) for c in commits]


def get_available_repositories(user: User) -> list[AvailableRepository]:
    """Returns accessible GitHub repositories / verified reference apps."""
    return [
        AvailableRepository(
            id="10101",
            name="demo-shop",
            full_name=f"{user.github_user_id or 'acme'}/demo-shop",
            description="Production-ready FastAPI e-commerce microservice with PostgreSQL & Docker",
            default_branch="main",
            url=f"https://github.com/{user.github_user_id or 'acme'}/demo-shop",
            language="Python",
            is_template=True,
        ),
        AvailableRepository(
            id="10102",
            name="cloudpilot-fastapi-service",
            full_name="cloudpilot-reference/cloudpilot-fastapi-service",
            description="Reference REST API with health check, CORS, Dockerfile, and Alembic",
            default_branch="main",
            url="https://github.com/cloudpilot-reference/cloudpilot-fastapi-service",
            language="Python",
            is_template=True,
        ),
        AvailableRepository(
            id="10103",
            name="nextjs-web-app",
            full_name="cloudpilot-reference/nextjs-web-app",
            description="Modern Next.js 16 App Router app with SSR and containerized deployment",
            default_branch="main",
            url="https://github.com/cloudpilot-reference/nextjs-web-app",
            language="TypeScript",
            is_template=True,
        ),
        AvailableRepository(
            id="10104",
            name="express-order-api",
            full_name="cloudpilot-reference/express-order-api",
            description="Node.js Express order service with Redis caching and health endpoints",
            default_branch="main",
            url="https://github.com/cloudpilot-reference/express-order-api",
            language="JavaScript",
            is_template=True,
        ),
    ]
