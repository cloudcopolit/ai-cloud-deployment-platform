"""Repositories, branches and commits, read from GitHub (ADR-021). Metadata only: source code
is never stored. Every SHA in the database came from GitHub."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.permissions import get_project_for_user, get_repository_for_user
from app.integrations.github_app import CommitInfo, GitHubClient, parse_repository_url
from app.models import Branch, Commit, Project, Repository, User
from app.modules.repositories.schemas import (
    BranchRead,
    CommitRead,
    DeploymentBranchUpdate,
    GitHubAccessRead,
    RepositoryConnect,
    RepositoryRead,
)

COMMITS_PER_SYNC = 30


def _to_repo_read(db: Session, repo: Repository, *, truncated: bool = False) -> RepositoryRead:
    deployment_branch = db.scalar(
        select(Branch.name).where(
            Branch.repository_id == repo.id, Branch.is_deployment_branch.is_(True)
        )
    )
    branch_count = db.scalar(
        select(func.count()).select_from(Branch).where(Branch.repository_id == repo.id)
    )
    return RepositoryRead(
        id=repo.id,
        project_id=repo.project_id,
        github_repository_id=repo.github_repository_id,
        owner=repo.owner,
        name=repo.name,
        url=repo.url,
        default_branch=repo.default_branch,
        deployment_branch=deployment_branch,
        is_private=repo.is_private,
        access_mode=repo.access_mode,
        branch_count=branch_count or 0,
        branches_truncated=truncated,
        connected_at=repo.connected_at,
        updated_at=repo.updated_at,
        last_synced_at=repo.last_synced_at,
    )


def _ensure_active(project: Project) -> None:
    if project.status != "ACTIVE":
        raise Conflict("The project is archived; it accepts no new work.")


def _sync_branches(db: Session, github: GitHubClient, repo: Repository) -> bool:
    """Mirror GitHub's branch list (adds new, removes vanished non-deployment branches)."""
    branches, truncated = github.list_branches(repo.owner, repo.name)
    remote = {b.name for b in branches}
    existing = {
        b.name: b for b in db.scalars(select(Branch).where(Branch.repository_id == repo.id))
    }
    for name in remote - existing.keys():
        db.add(Branch(repository_id=repo.id, name=name, is_default=name == repo.default_branch))
    for name, branch in existing.items():
        branch.is_default = name == repo.default_branch
        if name not in remote and not truncated and not branch.is_deployment_branch:
            has_commits = db.scalar(select(Commit.id).where(Commit.branch_id == branch.id))
            if has_commits is None:  # history rows keep their branch; never delete those
                db.delete(branch)
    db.flush()
    return truncated


def upsert_commits(
    db: Session, repo: Repository, branch: Branch, commits: list[CommitInfo]
) -> list[Commit]:
    """Idempotent on (repository_id, sha); a commit keeps the branch it was first seen on."""
    shas = [c.sha for c in commits]
    known = {
        c.sha: c
        for c in db.scalars(
            select(Commit).where(Commit.repository_id == repo.id, Commit.sha.in_(shas))
        )
    }
    rows: list[Commit] = []
    for info in commits:
        row = known.get(info.sha)
        if row is None:
            row = Commit(
                repository_id=repo.id,
                branch_id=branch.id,
                sha=info.sha,
                message=info.message,
                author_name=info.author_name,
                author_email=info.author_email,
                committed_at=info.committed_at,
            )
            db.add(row)
            known[info.sha] = row
        rows.append(row)
    db.flush()
    return rows


def _branch_by_name(db: Session, repo: Repository, name: str) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.repository_id == repo.id, Branch.name == name))
    if branch is None:
        raise NotFound(f"Branch '{name}' is not known for this repository. Sync it first.")
    return branch


# ───────────────────────── use cases ─────────────────────────


def list_project_repositories(db: Session, project_id: UUID, user: User) -> list[RepositoryRead]:
    get_project_for_user(db, user, project_id)
    repos = db.scalars(
        select(Repository)
        .where(Repository.project_id == project_id)
        .order_by(Repository.connected_at.desc())
    ).all()
    return [_to_repo_read(db, r) for r in repos]


def get_repository_details(db: Session, repo_id: UUID, user: User) -> RepositoryRead:
    repo, _ = get_repository_for_user(db, user, repo_id)
    return _to_repo_read(db, repo)


def connect_repository(
    db: Session, github: GitHubClient, project_id: UUID, user: User, data: RepositoryConnect
) -> RepositoryRead:
    project = get_project_for_user(db, user, project_id, "ADMIN")
    _ensure_active(project)
    owner, name = parse_repository_url(data.url)
    info = github.get_repository(owner, name)

    duplicate = db.scalar(
        select(Repository.id).where(
            Repository.project_id == project_id,
            Repository.github_repository_id == info.github_id,
        )
    )
    if duplicate:
        raise Conflict(f"{info.owner}/{info.name} is already connected to this project.")

    repo = Repository(
        project_id=project_id,
        github_repository_id=info.github_id,
        owner=info.owner,
        name=info.name,
        url=info.html_url,
        default_branch=info.default_branch,
        is_private=info.private,
        access_mode=info.access_mode,
    )
    db.add(repo)
    db.flush()

    truncated = _sync_branches(db, github, repo)
    default = db.scalar(
        select(Branch).where(Branch.repository_id == repo.id, Branch.name == info.default_branch)
    )
    if default is None:  # pragma: no cover - GitHub always lists the default branch
        raise BadRequest("GitHub did not return the repository's default branch.")
    default.is_deployment_branch = True
    db.flush()
    upsert_commits(
        db,
        repo,
        default,
        github.list_commits(repo.owner, repo.name, default.name, COMMITS_PER_SYNC),
    )
    repo.last_synced_at = datetime.now(UTC)
    db.commit()
    db.refresh(repo)
    return _to_repo_read(db, repo, truncated=truncated)


def sync_repository(db: Session, github: GitHubClient, repo_id: UUID, user: User) -> RepositoryRead:
    """Refresh metadata, branches and the deployment branch's latest commits from GitHub."""
    repo, project = get_repository_for_user(db, user, repo_id)
    _ensure_active(project)
    info = github.get_repository(repo.owner, repo.name)
    if info.github_id != repo.github_repository_id:
        raise Conflict("The GitHub repository at this name is a different repository now.")
    repo.owner, repo.name, repo.url = info.owner, info.name, info.html_url
    repo.default_branch, repo.is_private, repo.access_mode = (
        info.default_branch,
        info.private,
        info.access_mode,
    )
    truncated = _sync_branches(db, github, repo)
    deployment = db.scalar(
        select(Branch).where(Branch.repository_id == repo.id, Branch.is_deployment_branch.is_(True))
    )
    if deployment is not None:
        upsert_commits(
            db,
            repo,
            deployment,
            github.list_commits(repo.owner, repo.name, deployment.name, COMMITS_PER_SYNC),
        )
    repo.last_synced_at = datetime.now(UTC)
    db.commit()
    db.refresh(repo)
    return _to_repo_read(db, repo, truncated=truncated)


def list_repository_branches(db: Session, repo_id: UUID, user: User) -> list[BranchRead]:
    repo, _ = get_repository_for_user(db, user, repo_id)
    branches = db.scalars(
        select(Branch)
        .where(Branch.repository_id == repo.id)
        .order_by(Branch.is_deployment_branch.desc(), Branch.is_default.desc(), Branch.name)
    ).all()
    return [BranchRead.model_validate(b) for b in branches]


def set_deployment_branch(
    db: Session, repo_id: UUID, user: User, data: DeploymentBranchUpdate
) -> BranchRead:
    repo, project = get_repository_for_user(db, user, repo_id, "ADMIN")
    _ensure_active(project)
    target = _branch_by_name(db, repo, data.branch_name)
    current = db.scalar(
        select(Branch).where(Branch.repository_id == repo.id, Branch.is_deployment_branch.is_(True))
    )
    if current is not None and current.id != target.id:
        current.is_deployment_branch = False
        db.flush()  # the partial unique index allows only one deployment branch
    target.is_deployment_branch = True
    db.commit()
    db.refresh(target)
    return BranchRead.model_validate(target)


def list_repository_commits(
    db: Session,
    github: GitHubClient,
    repo_id: UUID,
    user: User,
    *,
    branch_name: str | None,
    refresh: bool,
    limit: int,
    offset: int,
) -> list[CommitRead]:
    """Commits of a branch. ``refresh`` pulls the latest page from GitHub first (real SHAs)."""
    repo, _ = get_repository_for_user(db, user, repo_id)
    if branch_name is None:
        branch = db.scalar(
            select(Branch).where(
                Branch.repository_id == repo.id, Branch.is_deployment_branch.is_(True)
            )
        )
        if branch is None:
            return []
    else:
        branch = _branch_by_name(db, repo, branch_name)

    if refresh:
        fetched = upsert_commits(
            db,
            repo,
            branch,
            github.list_commits(repo.owner, repo.name, branch.name, limit + offset),
        )
        db.commit()
        return [CommitRead.model_validate(c) for c in fetched[offset : offset + limit]]

    commits = db.scalars(
        select(Commit)
        .where(Commit.repository_id == repo.id, Commit.branch_id == branch.id)
        .order_by(Commit.committed_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [CommitRead.model_validate(c) for c in commits]


def resolve_commit(
    db: Session, github: GitHubClient, repo: Repository, branch_name: str | None, sha: str | None
) -> Commit:
    """The commit to analyze/deploy: an explicit SHA (verified on GitHub) or the branch head."""
    branch_name = branch_name or db.scalar(
        select(Branch.name).where(
            Branch.repository_id == repo.id, Branch.is_deployment_branch.is_(True)
        )
    )
    if branch_name is None:
        raise BadRequest("Choose a branch first.")
    branch = _branch_by_name(db, repo, branch_name)
    if sha:
        known = db.scalar(select(Commit).where(Commit.repository_id == repo.id, Commit.sha == sha))
        if known is not None:
            return known
        info = github.get_commit(repo.owner, repo.name, sha)
        return upsert_commits(db, repo, branch, [info])[0]
    head = github.list_commits(repo.owner, repo.name, branch.name, 1)
    if not head:
        raise BadRequest(f"Branch '{branch.name}' has no commits.")
    return upsert_commits(db, repo, branch, head)[0]


def github_access(github: GitHubClient) -> GitHubAccessRead:
    status = github.access_status()
    install_url = (
        f"https://github.com/apps/{settings.github_app_slug}/installations/new"
        if settings.github_app_slug
        else None
    )
    return GitHubAccessRead(
        app_configured=status.app_configured,
        app_installations=status.app_installations,
        app_install_url=install_url,
        token_configured=status.token_configured,
        rate_limit_remaining=status.rate_limit_remaining,
        rate_limit_limit=status.rate_limit_limit,
        mode_for_public_repos=status.mode_for_public_repos,
        webhook_enabled=bool(settings.github_webhook_secret),
    )
