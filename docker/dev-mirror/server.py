"""Dev-only GitHub mirror for CloudPilot's own example apps (never used in production).

Serves every directory under /examples as the repository cloudpilot-examples/<dir>, with one
commit on `main` whose SHA is derived from the files, through the same tiny GitHub API the
end-to-end fake server implements (e2e/fake_github/server.py is imported, not modified).

    python -I /mirror/server.py 8080
"""

from __future__ import annotations

import json
import sys
import zlib
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/fake")
import server as fake  # noqa: E402  (e2e/fake_github/server.py, mounted read-only)

OWNER = "cloudpilot-examples"
SKIP = {"__pycache__", ".git", "node_modules", ".venv"}
MAX_BYTES = 200_000


def _files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or any(p in SKIP for p in path.parts):
            continue
        if path.stat().st_size > MAX_BYTES:
            continue
        try:
            out[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return out


def _repos(examples: Path) -> dict[str, dict]:
    repos: dict[str, dict] = {}
    for directory in sorted(p for p in examples.iterdir() if p.is_dir()):
        full = f"{OWNER}/{directory.name}"
        files = _files(directory)
        sha = fake._sha(f"{full}/main/0/{json.dumps(files, sort_keys=True)}")
        commit = {
            "sha": sha,
            "commit": {
                "message": f"{directory.name}: CloudPilot example app",
                "author": {"name": "CloudPilot", "email": "examples@cloudpilot.invalid", "date": "2026-10-26T00:00:00Z"},
                "committer": {"date": "2026-10-26T00:00:00Z"},
            },
        }
        repos[full.lower()] = {
            "owner": OWNER,
            "name": directory.name,
            # far above real GitHub ids (~1.4e9 in 2026) and any seeded fake ids
            "id": 8_000_000_000 + zlib.crc32(full.encode()) % 1_000_000,
            "default_branch": "main",
            "branches": {"main": [commit]},
            "trees": {sha: files},
        }
    return repos


if __name__ == "__main__":
    fake.REPOS.clear()
    fake.REPOS.update(_repos(Path("/examples")))
    print("dev mirror serving:", ", ".join(sorted(fake.REPOS)), flush=True)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ThreadingHTTPServer(("0.0.0.0", port), fake.Handler).serve_forever()  # noqa: S104 - container only
