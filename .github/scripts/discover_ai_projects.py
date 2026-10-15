#!/usr/bin/env python3
"""Discover the Python projects under ai/ so CI never needs a hard-coded list.

A project is any directory under ai/ that contains a pyproject.toml or a
requirements.txt. Every project gets its own CI matrix entry (lint, type check,
tests). The script fails when the layout would let code escape those checks:

* a Python file that does not belong to any project, or
* a project that has no pytest test files.

Prints a JSON summary. When GITHUB_OUTPUT is set it also writes the `matrix`
and `count` outputs consumed by .github/workflows/ai.yml.

Usage: python .github/scripts/discover_ai_projects.py [ai-root]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import PurePosixPath

MANIFESTS = ("pyproject.toml", "requirements.txt")
MYPY_CONFIGS = ("mypy.ini", ".mypy.ini")
DEFAULT_PYTHON = "3.12"


def list_files(root: str) -> list[PurePosixPath]:
    """Tracked and untracked-but-not-ignored files, so local runs match CI."""
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", root],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [PurePosixPath(line) for line in output.splitlines() if os.path.isfile(line)]


def is_test_file(path: PurePosixPath) -> bool:
    return path.suffix == ".py" and (path.name.startswith("test_") or path.stem.endswith("_test"))


def owner(path: PurePosixPath, projects: list[PurePosixPath]) -> PurePosixPath | None:
    """The innermost project that contains `path`."""
    containing = [p for p in projects if p == path or p in path.parents]
    return max(containing, key=lambda p: len(p.parts), default=None)


def has_mypy_config(project: PurePosixPath) -> bool:
    if any(os.path.isfile(project / name) for name in MYPY_CONFIGS):
        return True
    pyproject = project / "pyproject.toml"
    if os.path.isfile(pyproject):
        with open(pyproject, encoding="utf-8") as handle:
            return "[tool.mypy]" in handle.read()
    return False


def python_version(project: PurePosixPath) -> str:
    version_file = project / ".python-version"
    if os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as handle:
            return handle.read().strip() or DEFAULT_PYTHON
    return DEFAULT_PYTHON


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "ai"
    files = list_files(root)
    projects = sorted({f.parent for f in files if f.name in MANIFESTS})

    errors: list[str] = []
    entries = []
    for project in projects:
        own_files = [f for f in files if owner(f, projects) == project]
        nested = [str(p.relative_to(project)) for p in projects if project in p.parents]
        if not any(is_test_file(f) for f in own_files):
            errors.append(f"{project}: no pytest test files (test_*.py or *_test.py) found.")
        entries.append(
            {
                "path": str(project),
                "name": str(project.relative_to(root)),
                "python": python_version(project),
                "install": "pyproject" if (project / "pyproject.toml") in files else "requirements",
                "own_mypy_config": has_mypy_config(project),
                "nested": nested,
            }
        )

    for path in files:
        if path.suffix == ".py" and owner(path, projects) is None:
            errors.append(
                f"{path}: Python file is not inside an AI project. Add a pyproject.toml or "
                "requirements.txt to its project directory (see ai/README.md)."
            )

    print(json.dumps({"projects": entries, "errors": errors}, indent=2))

    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"matrix={json.dumps({'include': entries})}\n")
            handle.write(f"count={len(entries)}\n")

    for error in errors:
        print(f"::error::{error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
