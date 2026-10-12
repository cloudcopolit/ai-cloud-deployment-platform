"""Repository scanner supporting Guided Mode and Standalone Auto-Scan Mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.code_analyzer.repository_analyzer import (
    FRAMEWORK_DEPENDENCIES,
    RepositoryAnalysis,
)
from agents.validator.models import ScanTarget

COMMON_ENTRY_POINT_CANDIDATES = (
    "app/main.py",
    "main.py",
    "app.py",
    "server.py",
    "src/main.py",
    "src/app.py",
    "run.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
)

COMMON_TEST_DIR_CANDIDATES = (
    "tests",
    "test",
    "ai/tests",
    "backend/tests",
)

COMMON_REQUIREMENTS_CANDIDATES = (
    "requirements.txt",
    "requirements-dev.txt",
    "dev-requirements.txt",
    "pyproject.toml",
    "Pipfile",
)

COMMON_CONFIG_CANDIDATES = (
    ".env.example",
    ".env.sample",
    ".env.template",
    "example.env",
    ".env",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
)


def scan_repository_standalone(repo_path: Path | str) -> ScanTarget:
    """Heuristically inspect a repository on disk without an upstream analysis report."""
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {root}")

    project_name = root.name

    # Discover requirements
    requirements_files: list[str] = []
    for candidate in COMMON_REQUIREMENTS_CANDIDATES:
        p = root / candidate
        if p.is_file():
            requirements_files.append(p.relative_to(root).as_posix())

    # Discover entry points
    entry_points: list[str] = []
    for candidate in COMMON_ENTRY_POINT_CANDIDATES:
        p = root / candidate
        if p.is_file():
            entry_points.append(p.relative_to(root).as_posix())

    # Discover test suites
    test_dirs: list[str] = []
    for candidate in COMMON_TEST_DIR_CANDIDATES:
        p = root / candidate
        if p.is_dir() and any(p.glob("test_*.py")):
            test_dirs.append(p.relative_to(root).as_posix())

    # Discover config files
    config_files: list[str] = []
    for candidate in COMMON_CONFIG_CANDIDATES:
        p = root / candidate
        if p.is_file():
            config_files.append(p.relative_to(root).as_posix())

    # Infer frameworks from requirements or manifest files
    frameworks: set[str] = set()
    req_file = root / "requirements.txt"
    if req_file.is_file():
        try:
            content = req_file.read_text(encoding="utf-8", errors="replace").lower()
            for dep, framework in FRAMEWORK_DEPENDENCIES.items():
                if dep in content:
                    frameworks.add(framework)
        except OSError:
            pass

    pyproject_file = root / "pyproject.toml"
    if pyproject_file.is_file():
        try:
            content = pyproject_file.read_text(encoding="utf-8", errors="replace").lower()
            for dep, framework in FRAMEWORK_DEPENDENCIES.items():
                if dep in content:
                    frameworks.add(framework)
        except OSError:
            pass

    return ScanTarget(
        project_name=project_name,
        repo_path=str(root),
        requirements_files=tuple(sorted(requirements_files)),
        entry_points=tuple(sorted(entry_points)),
        test_dirs=tuple(sorted(test_dirs)),
        config_files=tuple(sorted(config_files)),
        frameworks=tuple(sorted(frameworks)),
        is_guided=False,
    )


def resolve_scan_target(
    repo_path: Path | str,
    guided_input: RepositoryAnalysis | dict[str, Any] | str | Path | None = None,
) -> ScanTarget:
    """Resolve validation target metadata using either Guided Mode or Standalone Auto-Scan."""
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {root}")

    if guided_input is None:
        return scan_repository_standalone(root)

    # Ingest guided input
    analysis_dict: dict[str, Any] = {}
    if isinstance(guided_input, RepositoryAnalysis):
        analysis_dict = {
            "project_name": guided_input.project_name,
            "entry_points": list(guided_input.entry_points),
            "dependencies": list(guided_input.dependencies),
            "frameworks": list(guided_input.frameworks),
            "config_files": list(guided_input.config_files),
        }
    elif isinstance(guided_input, dict):
        analysis_dict = guided_input
    elif isinstance(guided_input, (str, Path)):
        candidate_path = Path(guided_input)
        if candidate_path.is_file():
            text = candidate_path.read_text(encoding="utf-8")
            analysis_dict = json.loads(text)
        else:
            try:
                analysis_dict = json.loads(str(guided_input))
            except json.JSONDecodeError:
                # If not valid JSON string, fall back to standalone
                return scan_repository_standalone(root)

    raw_name = str(analysis_dict.get("project_name") or "").strip()
    project_name = root.name if (not raw_name or raw_name == "unknown-project") else raw_name
    entry_points = [
        str(ep)
        for ep in analysis_dict.get("entry_points", [])
        if (root / ep).is_file()
    ]
    frameworks = [str(f) for f in analysis_dict.get("frameworks", [])]
    config_files = [
        str(cf)
        for cf in analysis_dict.get("config_files", [])
        if (root / cf).is_file()
    ]

    # Discover requirements files from reported config_files or on-disk fallback
    req_files: list[str] = [
        cf for cf in config_files if cf in COMMON_REQUIREMENTS_CANDIDATES
    ]
    if not req_files:
        for candidate in COMMON_REQUIREMENTS_CANDIDATES:
            if (root / candidate).is_file():
                req_files.append(candidate)

    # Discover test directories
    test_dirs: list[str] = []
    for candidate in COMMON_TEST_DIR_CANDIDATES:
        p = root / candidate
        if p.is_dir() and any(p.glob("test_*.py")):
            test_dirs.append(candidate)

    # Fall back to auto-discovered entry points if none in guided report
    if not entry_points:
        for candidate in COMMON_ENTRY_POINT_CANDIDATES:
            if (root / candidate).is_file():
                entry_points.append(candidate)

    return ScanTarget(
        project_name=project_name,
        repo_path=str(root),
        requirements_files=tuple(sorted(set(req_files))),
        entry_points=tuple(sorted(set(entry_points))),
        test_dirs=tuple(sorted(set(test_dirs))),
        config_files=tuple(sorted(set(config_files))),
        frameworks=tuple(sorted(set(frameworks))),
        is_guided=True,
    )
