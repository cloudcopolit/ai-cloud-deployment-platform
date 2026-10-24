from __future__ import annotations

import base64

import httpx

from AI.domain.analysis.models import RepositoryRef
from AI.domain.shared.errors import RepositoryAccessError

GITHUB_API_BASE = "https://api.github.com"


class GitHubRepositoryReader:
    """Fetches a pinned repository file tree and individual files via the GitHub REST API."""

    def __init__(self, *, base_url: str = GITHUB_API_BASE, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def _headers(self, access_token: str) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    async def list_files(self, repo: RepositoryRef, access_token: str = "") -> tuple[str, ...]:
        url = f"{self._base_url}/repos/{repo.owner}/{repo.name}/git/trees/{repo.commit_sha}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                params={"recursive": "1"},
                headers=self._headers(access_token),
            )
        if resp.status_code in (401, 403, 404):
            raise RepositoryAccessError(
                f"Cannot access repository {repo.full_name}@{repo.commit_sha} (HTTP {resp.status_code})"
            )
        if resp.status_code >= 400:
            raise RepositoryAccessError(f"GitHub API error {resp.status_code} listing files")

        data = resp.json()
        tree = data.get("tree", [])
        return tuple(
            item["path"]
            for item in tree
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        )

    async def read_file(
        self, repo: RepositoryRef, path: str, access_token: str = ""
    ) -> str:
        clean_path = path.lstrip("/")
        url = f"{self._base_url}/repos/{repo.owner}/{repo.name}/contents/{clean_path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                params={"ref": repo.commit_sha},
                headers=self._headers(access_token),
            )
        if resp.status_code in (401, 403, 404):
            raise RepositoryAccessError(
                f"Cannot read file {clean_path} in {repo.full_name}@{repo.commit_sha} (HTTP {resp.status_code})"
            )
        if resp.status_code >= 400:
            raise RepositoryAccessError(f"GitHub API error {resp.status_code} reading {clean_path}")

        data = resp.json()
        if isinstance(data, dict) and data.get("encoding") == "base64" and "content" in data:
            raw_bytes = base64.b64decode(data["content"])
            return raw_bytes.decode("utf-8", errors="replace")
        return ""
