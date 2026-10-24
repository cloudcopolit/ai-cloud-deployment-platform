from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from AI.domain.analysis.models import RepositoryRef
from AI.domain.shared.errors import RepositoryAccessError

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class LocalRepositoryReader:
    """Reads a local folder on disk so you can test the Analysis Agent on any local project."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()
        if not self._root.is_dir():
            raise RepositoryAccessError(f"Local directory does not exist: {self._root}")

    async def list_files(self, repo: RepositoryRef, access_token: str = "") -> tuple[str, ...]:
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in IGNORED_DIRS and not d.startswith(".venv") and not d.startswith("venv")
            ]
            for fname in filenames:
                if fname == "analysis_report.json" or fname.endswith(".pyc"):
                    continue
                full = Path(dirpath) / fname
                rel = full.relative_to(self._root).as_posix()
                files.append(rel)
        return tuple(sorted(files))

    async def read_file(self, repo: RepositoryRef, path: str, access_token: str = "") -> str:
        clean = PurePosixPath(path.lstrip("/"))
        target = (self._root / Path(clean)).resolve()
        # Prevent path traversal outside root_dir
        if self._root not in target.parents and target != self._root:
            raise RepositoryAccessError(f"Path '{path}' is outside repository root")
        if not target.is_file():
            raise RepositoryAccessError(f"File '{path}' does not exist in {self._root}")
        return target.read_text(encoding="utf-8", errors="replace")
