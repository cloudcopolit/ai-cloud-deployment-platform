"""RepositoryGateway for the AI layer, backed by the GitHub client (06 §6 Communication Module).

The AI layer sees paths and bytes only. Credentials are resolved inside GitHubClient and never
cross this boundary; backend errors become contract ErrorInfo codes.
"""

from __future__ import annotations

from cloudpilot_ai.contracts import ErrorCode, Stage
from cloudpilot_ai.errors import AgentError
from cloudpilot_ai.ports import FileEntry, FileListing

from app.core.errors import (
    CloudPilotError,
    GitHubRateLimited,
    GitHubUnauthorized,
    NotFound,
    RepositoryNotFound,
    RepositoryTooLarge,
)
from app.integrations.github_app import GitHubClient

_CODES: list[tuple[type[CloudPilotError], ErrorCode, bool]] = [
    (GitHubRateLimited, ErrorCode.GITHUB_RATE_LIMITED, True),
    (GitHubUnauthorized, ErrorCode.GITHUB_UNAUTHORIZED, False),
    (RepositoryNotFound, ErrorCode.REPOSITORY_NOT_FOUND, False),
    (NotFound, ErrorCode.REPOSITORY_NOT_FOUND, False),
    (RepositoryTooLarge, ErrorCode.REPOSITORY_TOO_LARGE, False),
]


def _as_agent_error(exc: CloudPilotError) -> AgentError:
    for cls, code, retryable in _CODES:
        if isinstance(exc, cls):
            return AgentError.of(
                code, exc.message, stage=Stage.FETCH_REPOSITORY, retryable=retryable
            )
    return AgentError.of(
        ErrorCode.INTERNAL_ERROR,
        "GitHub could not be reached.",
        stage=Stage.FETCH_REPOSITORY,
        retryable=True,
    )


class GitHubRepositoryGateway:
    def __init__(self, client: GitHubClient, *, owner: str, name: str, sha: str) -> None:
        self._client = client
        self._owner, self._name, self._sha = owner, name, sha

    def list_files(self) -> FileListing:
        try:
            tree = self._client.get_tree(self._owner, self._name, self._sha)
        except CloudPilotError as exc:
            raise _as_agent_error(exc) from None
        return FileListing(
            entries=[FileEntry(path=e.path, size=e.size) for e in tree.entries],
            truncated=tree.truncated,
        )

    def read_file(self, path: str, max_bytes: int) -> bytes:
        try:
            return self._client.read_file(self._owner, self._name, self._sha, path, max_bytes)
        except CloudPilotError as exc:
            raise _as_agent_error(exc) from None
