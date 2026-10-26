"""GitHub webhook handling. The payload is untrusted: it is only used after the HMAC signature
matched, every field is validated, and only commit metadata is stored. Pushes never trigger a
deployment (Q-11: no auto-deploy)."""

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.github_app import CommitInfo
from app.models import Branch, Repository
from app.modules.repositories.service import upsert_commits

MAX_COMMITS_PER_PUSH = 100


def _str(value: object, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) and value else None


def _commit_from_payload(raw: object) -> CommitInfo | None:
    if not isinstance(raw, dict):
        return None
    sha = raw.get("id")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return None
    author = raw.get("author")
    author = author if isinstance(author, dict) else {}
    timestamp = raw.get("timestamp")
    try:
        committed_at = (
            datetime.fromisoformat(timestamp).astimezone(UTC)
            if isinstance(timestamp, str)
            else datetime.now(UTC)
        )
    except ValueError:
        committed_at = datetime.now(UTC)
    return CommitInfo(
        sha=sha.lower(),
        message=_str(raw.get("message"), 4000) or "",
        author_name=_str(author.get("name"), 255),
        author_email=_str(author.get("email"), 320),
        committed_at=committed_at,
    )


def handle_push(db: Session, payload: dict[str, Any]) -> int:
    """Record pushed commits on every connected repository whose deployment branch was pushed.
    Idempotent: a redelivered event inserts nothing new. Returns the number of commits seen."""
    repository = payload.get("repository")
    ref = payload.get("ref")
    if not isinstance(repository, dict) or not isinstance(ref, str):
        return 0
    if not ref.startswith("refs/heads/"):
        return 0  # tags are ignored
    branch_name = ref.removeprefix("refs/heads/")
    github_id = str(repository.get("id", ""))
    raw_commits = payload.get("commits")
    if not isinstance(raw_commits, list):
        return 0
    commits = [c for c in map(_commit_from_payload, raw_commits[:MAX_COMMITS_PER_PUSH]) if c]
    if not github_id or not commits:
        return 0

    seen = 0
    # The same GitHub repository may be connected to several projects (Q-3).
    for repo in db.scalars(select(Repository).where(Repository.github_repository_id == github_id)):
        branch = db.scalar(
            select(Branch).where(
                Branch.repository_id == repo.id,
                Branch.name == branch_name,
                Branch.is_deployment_branch.is_(True),
            )
        )
        if branch is None:
            continue
        upsert_commits(db, repo, branch, commits)
        seen += len(commits)
    db.commit()
    return seen
