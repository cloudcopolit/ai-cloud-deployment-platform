from __future__ import annotations

from typing import Protocol

from AI.domain.analysis.models import RepositoryRef


class RepositoryReader(Protocol):
    async def list_files(self, repo: RepositoryRef, access_token: str = "") -> tuple[str, ...]:
        """List all file paths in the repository at repo.commit_sha."""
        ...

    async def read_file(
        self, repo: RepositoryRef, path: str, access_token: str = ""
    ) -> str:
        """Read the raw text content of a single file at repo.commit_sha."""
        ...
