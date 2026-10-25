"""A tiny fake of the GitHub REST API and raw-content host for end-to-end tests.

Standard library only. Serves the repositories in repos.json; SHAs are derived from content
so they are stable across runs. Only the endpoints CloudPilot's GitHubClient uses exist.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

FIXTURES = Path(__file__).with_name("repos.json")


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()


def _load() -> dict[str, dict]:
    """repos.json: {"owner/name": {"id": 1, "default_branch": "main", "branches":
    {"main": [{"message": "...", "date": "...", "files": {path: content}}]}}} (oldest first)."""
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    repos: dict[str, dict] = {}
    for full, spec in data.items():
        owner, name = full.split("/")
        branches: dict[str, list[dict]] = {}
        trees: dict[str, dict[str, str]] = {}
        for branch, commits in spec["branches"].items():
            history: list[dict] = []
            files: dict[str, str] = {}
            for i, commit in enumerate(commits):
                files = {**files, **commit["files"]}
                sha = _sha(f"{full}/{branch}/{i}/{commit['message']}/{json.dumps(files, sort_keys=True)}")
                trees[sha] = dict(files)
                history.insert(
                    0,
                    {
                        "sha": sha,
                        "commit": {
                            "message": commit["message"],
                            "author": {"name": "E2E Bot", "email": "e2e@example.com", "date": commit["date"]},
                            "committer": {"date": commit["date"]},
                        },
                    },
                )
            branches[branch] = history
        repos[full.lower()] = {
            "owner": owner,
            "name": name,
            "id": spec["id"],
            "default_branch": spec.get("default_branch", "main"),
            "branches": branches,
            "trees": trees,
        }
    return repos


REPOS = _load()


class Handler(BaseHTTPRequestHandler):
    server_version = "fake-github/1"

    def log_message(self, fmt: str, *args: object) -> None:  # quiet
        sys.stderr.write("fake-github " + (fmt % args) + "\n")

    def _json(self, status: int, body: object) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _text(self, status: int, body: str) -> None:
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        url = urlsplit(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path
        if path == "/rate_limit":
            return self._json(200, {"resources": {"core": {"limit": 5000, "remaining": 4999}}})
        if path == "/app/installations":
            return self._json(200, [])
        raw = re.match(r"^/raw/([^/]+)/([^/]+)/([0-9a-f]{40})/(.+)$", path)
        if raw:
            repo = REPOS.get(f"{raw.group(1)}/{raw.group(2)}".lower())
            content = repo["trees"].get(raw.group(3), {}).get(raw.group(4)) if repo else None
            return self._text(200, content) if content is not None else self._text(404, "")
        m = re.match(r"^/repos/([^/]+)/([^/]+)(/.*)?$", path)
        repo = REPOS.get(f"{m.group(1)}/{m.group(2)}".lower()) if m else None
        if not m or repo is None:
            return self._json(404, {"message": "Not Found"})
        rest = m.group(3) or ""
        if rest == "":
            return self._json(
                200,
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "owner": {"login": repo["owner"]},
                    "html_url": f"https://github.com/{repo['owner']}/{repo['name']}",
                    "default_branch": repo["default_branch"],
                    "private": False,
                    "size": 10,
                },
            )
        if rest == "/installation":
            return self._json(404, {"message": "Not Found"})
        if rest == "/branches":
            return self._json(
                200, [{"name": b, "commit": {"sha": h[0]["sha"]}} for b, h in sorted(repo["branches"].items())]
            )
        if rest == "/commits":
            history = repo["branches"].get(query.get("sha", repo["default_branch"]))
            if history is None:
                return self._json(404, {"message": "No commit found"})
            return self._json(200, history[: int(query.get("per_page", "30"))])
        commit = re.match(r"^/commits/([0-9a-f]{40})$", rest)
        if commit:
            for history in repo["branches"].values():
                for c in history:
                    if c["sha"] == commit.group(1):
                        return self._json(200, c)
            return self._json(422, {"message": "No commit found for SHA"})
        tree = re.match(r"^/git/trees/([0-9a-f]{40})$", rest)
        if tree and tree.group(1) in repo["trees"]:
            files = repo["trees"][tree.group(1)]
            entries = [
                {"path": p, "mode": "100644", "type": "blob", "sha": _sha(c), "size": len(c.encode())}
                for p, c in sorted(files.items())
            ]
            return self._json(200, {"tree": entries, "truncated": False})
        return self._json(404, {"message": "Not Found"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 - container only
