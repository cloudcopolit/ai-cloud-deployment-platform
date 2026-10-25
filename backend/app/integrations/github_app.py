"""GitHub REST client for repository access (ADR-004, ADR-021).

Signing in uses the OAuth App in `github.py` (identity only). Reading repositories uses this
client. Credentials are resolved per repository, most privileged first:

1. GitHub App installation token: private and public repositories the App is installed on.
2. ``GITHUB_TOKEN``: a personal/fine-grained token, public repositories, 5000 requests/hour.
3. Anonymous: public repositories only, 60 requests/hour.

Tokens live in memory only, are never logged, and never leave this module. File contents of
public repositories are read from the raw content host, which does not use the API quota.
Nothing here executes repository content.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import jwt

from app.core.config import settings
from app.core.errors import (
    BadRequest,
    GitHubRateLimited,
    GitHubUnauthorized,
    NotFound,
    RepositoryNotFound,
    RepositoryTooLarge,
    UpstreamError,
)

AccessMode = Literal["GITHUB_APP", "TOKEN", "ANONYMOUS"]

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?"
_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
_URL_PATTERNS = (
    re.compile(rf"^https?://(?:www\.)?github\.com/(?P<owner>{_OWNER})/(?P<name>{_NAME})$"),
    re.compile(rf"^git@github\.com:(?P<owner>{_OWNER})/(?P<name>{_NAME})$"),
    re.compile(rf"^(?P<owner>{_OWNER})/(?P<name>{_NAME})$"),
)
_SHA = re.compile(r"^[0-9a-f]{40}$")

MAX_BRANCH_PAGES = 3  # 300 branches is plenty for a picker; more are reported as truncated
NOT_INSTALLED_TTL = 300  # seconds before re-checking whether the App was installed on a repo
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


@dataclass(frozen=True)
class RepoInfo:
    github_id: str
    owner: str
    name: str
    html_url: str
    default_branch: str
    private: bool
    size_kb: int
    access_mode: AccessMode


@dataclass(frozen=True)
class BranchInfo:
    name: str
    head_sha: str


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    message: str
    author_name: str | None
    author_email: str | None
    committed_at: datetime


@dataclass(frozen=True)
class TreeEntry:
    path: str
    size: int
    sha: str


@dataclass(frozen=True)
class Tree:
    entries: list[TreeEntry]
    truncated: bool


@dataclass(frozen=True)
class AccessStatus:
    """What this deployment can reach. Safe to show: contains no secrets."""

    app_configured: bool
    app_installations: int | None
    token_configured: bool
    rate_limit_remaining: int | None
    rate_limit_limit: int | None
    mode_for_public_repos: AccessMode


def parse_repository_url(value: str) -> tuple[str, str]:
    """Accept https://github.com/o/r(.git), git@github.com:o/r.git or o/r. Raises BadRequest."""
    candidate = value.strip().rstrip("/").removesuffix(".git")
    for pattern in _URL_PATTERNS:
        match = pattern.match(candidate)
        if match and match.group("name") not in {"", ".", ".."}:
            return match.group("owner"), match.group("name")
    raise BadRequest(
        "Not a GitHub repository URL. Use https://github.com/<owner>/<repository>.",
        details={"field": "url"},
    )


def verify_webhook_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Constant-time check of ``X-Hub-Signature-256`` (``sha256=<hex>``)."""
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class GitHubClient:
    """Thin, synchronous GitHub client. Returns DTOs, raises domain errors, holds no state
    except short-lived installation tokens cached in memory."""

    def __init__(
        self,
        *,
        api_url: str,
        raw_url: str,
        token: str | None = None,
        app_id: str | None = None,
        app_private_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._raw_url = raw_url.rstrip("/")
        self._token = token or None
        self._app_id = app_id or None
        self._app_key = app_private_key or None
        self._clock = clock
        self._sleep = sleep
        self._http = httpx.Client(
            transport=transport,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": "CloudPilot", "X-GitHub-Api-Version": "2022-11-28"},
            follow_redirects=False,
        )
        self._lock = threading.Lock()
        self._installation_tokens: dict[str, tuple[str, float]] = {}

    def close(self) -> None:
        self._http.close()

    # ───────────────────────── credentials ─────────────────────────
    @property
    def app_configured(self) -> bool:
        return bool(self._app_id and self._app_key)

    def _app_jwt(self) -> str:
        now = int(self._clock())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self._app_id}
        return jwt.encode(payload, self._app_key or "", algorithm="RS256")

    def _installation_token(self, owner: str, name: str) -> str | None:
        """Installation token for this repository, or None when the App is not installed on it."""
        if not self.app_configured:
            return None
        key = f"{owner}/{name}".lower()
        with self._lock:
            cached = self._installation_tokens.get(key)
            if cached and cached[1] - 60 > self._clock():
                return cached[0] or None  # "" = known not installed (negative cache)
        app_headers = {"Authorization": f"Bearer {self._app_jwt()}"}
        lookup = self._send("GET", f"/repos/{owner}/{name}/installation", headers=app_headers)
        if lookup.status_code == 404:
            with self._lock:
                self._installation_tokens[key] = ("", self._clock() + NOT_INSTALLED_TTL)
            return None
        self._raise_for_status(lookup, owner, name)
        installation_id = lookup.json()["id"]
        minted = self._send(
            "POST", f"/app/installations/{installation_id}/access_tokens", headers=app_headers
        )
        self._raise_for_status(minted, owner, name)
        data = minted.json()
        expires = _parse_time(data["expires_at"]).timestamp()
        with self._lock:
            self._installation_tokens[key] = (data["token"], expires)
        return str(data["token"])

    def _auth(self, owner: str, name: str) -> tuple[AccessMode, dict[str, str]]:
        installation = self._installation_token(owner, name)
        if installation:
            return "GITHUB_APP", {"Authorization": f"Bearer {installation}"}
        if self._token:
            return "TOKEN", {"Authorization": f"Bearer {self._token}"}
        return "ANONYMOUS", {}

    # ───────────────────────── transport ─────────────────────────
    def _send(
        self,
        method: str,
        path_or_url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("http") else f"{self._api_url}{path_or_url}"
        merged = {"Accept": "application/vnd.github+json", **(headers or {})}
        last_error: Exception | None = None
        redirects = 0
        attempt = 0
        while attempt < 3:
            try:
                response = self._http.request(method, url, headers=merged, params=params)
            except httpx.TransportError as exc:  # network trouble: retry with back-off
                last_error = exc
            else:
                if response.status_code in {301, 302, 307, 308} and redirects < 3:
                    # Renamed/transferred repositories redirect. Follow only on the same host,
                    # so credentials are never sent anywhere else.
                    target = response.next_request.url if response.next_request else None
                    if target is None or target.host != httpx.URL(url).host:
                        raise UpstreamError("GitHub redirected to an unexpected host.")
                    url, params, redirects = str(target), None, redirects + 1
                    continue
                if response.status_code < 500:
                    return response
                last_error = UpstreamError(f"GitHub returned HTTP {response.status_code}.")
            self._sleep(0.25 * (2**attempt))
            attempt += 1
        raise UpstreamError(
            "GitHub is not reachable right now. Try again later.",
            details={"reason": type(last_error).__name__ if last_error else "unknown"},
        )

    def _raise_for_status(self, response: httpx.Response, owner: str, name: str) -> None:
        status = response.status_code
        if status < 400:
            return
        remaining = response.headers.get("x-ratelimit-remaining")
        if status == 429 or (status == 403 and remaining == "0"):
            reset = response.headers.get("x-ratelimit-reset")
            reset_at = (
                datetime.fromtimestamp(int(reset), UTC).isoformat()
                if reset and reset.isdigit()
                else None
            )
            raise GitHubRateLimited(
                "GitHub API rate limit reached. Add GITHUB_TOKEN or install the CloudPilot "
                "GitHub App for a higher limit.",
                details={"reset_at": reset_at},
            )
        if status == 404:
            raise RepositoryNotFound(
                f"Repository {owner}/{name} was not found or is not accessible. Private "
                "repositories require the CloudPilot GitHub App to be installed on them.",
            )
        if status in {401, 403}:
            raise GitHubUnauthorized("GitHub rejected CloudPilot's credentials for this request.")
        if status == 422:  # GitHub's answer for a SHA or ref it does not know
            raise NotFound(f"Commit or branch not found in {owner}/{name}.")
        if status == 409:  # e.g. an empty repository has no commits
            raise BadRequest(f"Repository {owner}/{name} has no commits yet.")
        raise UpstreamError(f"GitHub returned HTTP {status}.")

    def _get_json(
        self, owner: str, name: str, path: str, params: dict[str, Any] | None = None
    ) -> tuple[Any, AccessMode, httpx.Response]:
        mode, auth = self._auth(owner, name)
        response = self._send("GET", path, headers=auth, params=params)
        self._raise_for_status(response, owner, name)
        return response.json(), mode, response

    # ───────────────────────── repository API ─────────────────────────
    def get_repository(self, owner: str, name: str) -> RepoInfo:
        data, mode, _ = self._get_json(owner, name, f"/repos/{owner}/{name}")
        return RepoInfo(
            github_id=str(data["id"]),
            owner=data["owner"]["login"],
            name=data["name"],
            html_url=data["html_url"],
            default_branch=data.get("default_branch") or "main",
            private=bool(data.get("private")),
            size_kb=int(data.get("size") or 0),
            access_mode=mode,
        )

    def list_branches(self, owner: str, name: str) -> tuple[list[BranchInfo], bool]:
        """Branches (up to 300) and whether the list was cut off."""
        branches: list[BranchInfo] = []
        for page in range(1, MAX_BRANCH_PAGES + 1):
            data, _, response = self._get_json(
                owner, name, f"/repos/{owner}/{name}/branches", {"per_page": 100, "page": page}
            )
            branches.extend(BranchInfo(name=b["name"], head_sha=b["commit"]["sha"]) for b in data)
            if 'rel="next"' not in response.headers.get("link", ""):
                return branches, False
        return branches, True

    def list_commits(self, owner: str, name: str, branch: str, limit: int = 20) -> list[CommitInfo]:
        data, _, _ = self._get_json(
            owner,
            name,
            f"/repos/{owner}/{name}/commits",
            {"sha": branch, "per_page": max(1, min(limit, 100))},
        )
        return [self._commit_info(c) for c in data]

    def get_commit(self, owner: str, name: str, ref: str) -> CommitInfo:
        data, _, _ = self._get_json(owner, name, f"/repos/{owner}/{name}/commits/{ref}")
        return self._commit_info(data)

    @staticmethod
    def _commit_info(c: dict[str, Any]) -> CommitInfo:
        commit = c["commit"]
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        when = committer.get("date") or author.get("date")
        return CommitInfo(
            sha=c["sha"],
            message=(commit.get("message") or "")[:4000],
            author_name=(author.get("name") or None),
            author_email=(author.get("email") or None),
            committed_at=_parse_time(when) if when else datetime.now(UTC),
        )

    def get_tree(self, owner: str, name: str, sha: str) -> Tree:
        """Recursive file listing at a commit (blobs only; symlinks and submodules skipped)."""
        if not _SHA.match(sha):
            raise BadRequest("A full 40-character commit SHA is required.")
        data, _, _ = self._get_json(
            owner, name, f"/repos/{owner}/{name}/git/trees/{sha}", {"recursive": "1"}
        )
        entries = [
            TreeEntry(path=e["path"], size=int(e.get("size") or 0), sha=e["sha"])
            for e in data.get("tree", [])
            # 100644/100755 are regular files; 120000 = symlink, 160000 = submodule
            if e.get("type") == "blob" and e.get("mode") in {"100644", "100755"}
        ]
        return Tree(entries=entries, truncated=bool(data.get("truncated")))

    def read_file(self, owner: str, name: str, sha: str, path: str, max_bytes: int) -> bytes:
        """File content at a commit, at most ``max_bytes`` (RepositoryTooLarge beyond)."""
        if not _SHA.match(sha) or path.startswith("/") or ".." in path.split("/"):
            raise BadRequest("Invalid file reference.")
        mode, auth = self._auth(owner, name)
        if mode == "GITHUB_APP":
            url = f"{self._api_url}/repos/{owner}/{name}/contents/{path}"
            headers = {**auth, "Accept": "application/vnd.github.raw+json"}
            params: dict[str, Any] | None = {"ref": sha}
        else:  # public content host: no API quota used
            url = f"{self._raw_url}/{owner}/{name}/{sha}/{path}"
            headers, params = {}, None
        with self._http.stream("GET", url, headers=headers, params=params) as response:
            if response.status_code >= 400:
                response.read()
                self._raise_for_status(response, owner, name)
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise RepositoryTooLarge(f"{path} is larger than {max_bytes} bytes.")
                chunks.append(chunk)
        return b"".join(chunks)

    # ───────────────────────── status ─────────────────────────
    def access_status(self) -> AccessStatus:
        installations: int | None = None
        if self.app_configured:
            response = self._send(
                "GET", "/app/installations", headers={"Authorization": f"Bearer {self._app_jwt()}"}
            )
            installations = len(response.json()) if response.status_code == 200 else None
        auth = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        rate = self._send("GET", "/rate_limit", headers=auth)
        core = rate.json().get("resources", {}).get("core", {}) if rate.status_code == 200 else {}
        return AccessStatus(
            app_configured=self.app_configured,
            app_installations=installations,
            token_configured=bool(self._token),
            rate_limit_remaining=core.get("remaining"),
            rate_limit_limit=core.get("limit"),
            mode_for_public_repos="TOKEN" if self._token else "ANONYMOUS",
        )


def _read_private_key(path: str | None) -> str | None:
    if not path:
        return None
    key_file = Path(path)
    return key_file.read_text(encoding="utf-8") if key_file.is_file() else None


_client: GitHubClient | None = None
_client_lock = threading.Lock()


def get_github_client() -> GitHubClient:
    """FastAPI dependency / shared instance. Tests override it with a fake transport."""
    global _client
    with _client_lock:
        if _client is None:
            _client = GitHubClient(
                api_url=settings.github_api_url,
                raw_url=settings.github_raw_url,
                token=settings.github_token,
                app_id=settings.github_app_id,
                app_private_key=_read_private_key(settings.github_app_private_key_path),
            )
        return _client
