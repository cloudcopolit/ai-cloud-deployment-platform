"""Test doubles. No test talks to the network: GitHub is an in-memory fake behind
httpx.MockTransport, so the real GitHubClient code (auth, paging, errors) still runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx

from app.integrations.github_app import GitHubClient

API = "https://api.github.test"
RAW = "https://raw.github.test"


def sha_of(text: str) -> str:
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()


@dataclass
class FakeRepo:
    owner: str
    name: str
    github_id: int
    default_branch: str = "main"
    private: bool = False
    # branch -> list of commit dicts, newest first
    commits: dict[str, list[dict]] = field(default_factory=dict)
    # sha -> {path: content}
    files: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_commit(self, branch: str, message: str, files: dict[str, str] | None = None) -> str:
        history = self.commits.setdefault(branch, [])
        sha = sha_of(f"{self.owner}/{self.name}/{branch}/{len(history)}/{message}")
        when = datetime(2026, 10, 1, tzinfo=UTC) + timedelta(hours=len(history))
        history.insert(
            0,
            {
                "sha": sha,
                "commit": {
                    "message": message,
                    "author": {"name": "Dev", "email": "dev@example.com", "date": when.isoformat()},
                    "committer": {"date": when.isoformat().replace("+00:00", "Z")},
                },
            },
        )
        parent = history[1]["sha"] if len(history) > 1 else None
        self.files[sha] = {**(self.files.get(parent, {}) if parent else {}), **(files or {})}
        return sha


class FakeGitHub:
    """Serves the subset of the GitHub REST API and raw host that GitHubClient uses."""

    def __init__(self) -> None:
        self.repos: dict[str, FakeRepo] = {}
        self.requests: list[httpx.Request] = []
        self.rate_limited = False
        self.fail_with: int | None = None

    def add_repo(self, owner: str, name: str, **kwargs) -> FakeRepo:
        repo = FakeRepo(owner=owner, name=name, github_id=100_000 + len(self.repos), **kwargs)
        self.repos[f"{owner}/{name}".lower()] = repo
        return repo

    def client(self, **kwargs) -> GitHubClient:
        return GitHubClient(
            api_url=API,
            raw_url=RAW,
            transport=httpx.MockTransport(self.handle),
            sleep=lambda _: None,
            **kwargs,
        )

    # ───────────────────────── routing ─────────────────────────
    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with:
            return httpx.Response(self.fail_with)
        if self.rate_limited:
            return httpx.Response(
                403,
                headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1893456000"},
                json={"message": "API rate limit exceeded"},
            )
        url = urlsplit(str(request.url))
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if f"{url.scheme}://{url.netloc}" == RAW:
            return self._raw(url.path)
        path = url.path
        if path == "/rate_limit":
            return httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 57}}})
        if path == "/app/installations":
            return httpx.Response(200, json=[])
        match = re.match(r"^/repos/([^/]+)/([^/]+)(/.*)?$", path)
        if not match:
            return httpx.Response(404, json={"message": "Not Found"})
        repo = self.repos.get(f"{match.group(1)}/{match.group(2)}".lower())
        if repo is None:
            return httpx.Response(404, json={"message": "Not Found"})
        rest = match.group(3) or ""
        if repo.private and "authorization" not in request.headers:
            return httpx.Response(404, json={"message": "Not Found"})
        return self._repo_route(repo, rest, query)

    def _repo_route(self, repo: FakeRepo, rest: str, query: dict[str, str]) -> httpx.Response:
        if rest == "":
            return httpx.Response(
                200,
                json={
                    "id": repo.github_id,
                    "name": repo.name,
                    "owner": {"login": repo.owner},
                    "html_url": f"https://github.com/{repo.owner}/{repo.name}",
                    "default_branch": repo.default_branch,
                    "private": repo.private,
                    "size": 120,
                },
            )
        if rest == "/installation":
            return httpx.Response(404, json={"message": "Not Found"})
        if rest == "/branches":
            page = int(query.get("page", "1"))
            names = sorted(repo.commits)
            chunk = names[(page - 1) * 100 : page * 100]
            more = len(names) > page * 100
            headers = {"link": f'<{API}/x?page={page + 1}>; rel="next"'} if more else {}
            body = [{"name": n, "commit": {"sha": repo.commits[n][0]["sha"]}} for n in chunk]
            return httpx.Response(200, json=body, headers=headers)
        if rest == "/commits":
            branch = query.get("sha", repo.default_branch)
            if branch not in repo.commits:
                return httpx.Response(404, json={"message": "No commit found"})
            limit = int(query.get("per_page", "30"))
            return httpx.Response(200, json=repo.commits[branch][:limit])
        commit_match = re.match(r"^/commits/([0-9a-f]{40})$", rest)
        if commit_match:
            for history in repo.commits.values():
                for c in history:
                    if c["sha"] == commit_match.group(1):
                        return httpx.Response(200, json=c)
            return httpx.Response(422, json={"message": "No commit found for SHA"})
        tree_match = re.match(r"^/git/trees/([0-9a-f]{40})$", rest)
        if tree_match:
            files = repo.files.get(tree_match.group(1))
            if files is None:
                return httpx.Response(404, json={"message": "Not Found"})
            tree = [
                {
                    "path": p,
                    "mode": "100644",
                    "type": "blob",
                    "sha": sha_of(c),
                    "size": len(c.encode()),
                }
                for p, c in sorted(files.items())
            ]
            return httpx.Response(200, json={"tree": tree, "truncated": False})
        return httpx.Response(404, json={"message": "Not Found"})

    def _raw(self, path: str) -> httpx.Response:
        parts = path.lstrip("/").split("/", 3)
        if len(parts) < 4:
            return httpx.Response(404)
        owner, name, sha, file_path = parts
        repo = self.repos.get(f"{owner}/{name}".lower())
        content = repo.files.get(sha, {}).get(file_path) if repo else None
        if content is None:
            return httpx.Response(404)
        return httpx.Response(200, content=content.encode())


def push_payload(repo: FakeRepo, branch: str, shas: list[str]) -> bytes:
    commits = [
        {
            "id": sha,
            "message": f"commit {sha[:7]}",
            "timestamp": "2026-10-20T10:00:00+00:00",
            "author": {"name": "Dev", "email": "dev@example.com"},
        }
        for sha in shas
    ]
    return json.dumps(
        {"ref": f"refs/heads/{branch}", "repository": {"id": repo.github_id}, "commits": commits}
    ).encode()
