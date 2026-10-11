"""Deterministic repository-level analysis without executing project code."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from agents.code_analyzer.analyzer import (
    AnalysisReport,
    analyze_python_sources,
)
from workflows.repository import RepoSnapshot

ENTRY_POINT_NAMES = {
    "__main__.py",
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
}

CONFIG_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".env.example",
    "Procfile",
    "Makefile",
    "vercel.json",
    "serverless.yml",
    "serverless.yaml",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "poetry.lock",
    "package.json",
}

FRAMEWORK_DEPENDENCIES = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "streamlit": "Streamlit",
    "gradio": "Gradio",
    "chainlit": "Chainlit",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "celery": "Celery",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "transformers": "Hugging Face Transformers",
    "langchain": "LangChain",
}

LANGUAGE_SUFFIXES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C/C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".sql": "SQL",
}


@dataclass(frozen=True, slots=True)
class RepositoryAnalysis:
    """Summary of a repository and its Python source analysis."""

    project_name: str
    languages: tuple[str, ...]
    project_structure: tuple[str, ...]
    entry_points: tuple[str, ...]
    dependencies: tuple[str, ...]
    frameworks: tuple[str, ...]
    config_files: tuple[str, ...]
    python_analysis: AnalysisReport
    metadata_errors: tuple[str, ...] = ()


def _parse_requirement_name(requirement: str) -> str | None:
    """Extract a package name from a simple requirement declaration."""
    value = requirement.strip()

    if not value or value.startswith(("#", "-e ", "-r ", "--")):
        return None

    # Ignore environment markers and version constraints.
    for separator in (";", "[", "=", "<", ">", "!", "~"):
        value = value.split(separator, maxsplit=1)[0]

    value = value.strip()
    if not value:
        return None

    # Normalize package names for comparisons.
    return value.lower().replace("_", "-").replace(".", "-")


def _extract_pyproject_dependencies(
    content: str,
) -> tuple[str, ...]:
    """Extract dependencies from standard pyproject.toml sections."""
    data = tomllib.loads(content)
    project = data.get("project", {})
    dependencies = project.get("dependencies", [])

    names = {
        name
        for requirement in dependencies
        if isinstance(requirement, str)
        if (name := _parse_requirement_name(requirement)) is not None
    }

    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for requirements in optional.values():
            if not isinstance(requirements, list):
                continue
            names.update(
                name
                for requirement in requirements
                if isinstance(requirement, str)
                if (name := _parse_requirement_name(requirement)) is not None
            )

    # Support common Poetry metadata.
    poetry = data.get("tool", {}).get("poetry", {})
    poetry_dependencies = poetry.get("dependencies", {})
    if isinstance(poetry_dependencies, dict):
        names.update(name for name in poetry_dependencies if name.lower() != "python")

    return tuple(sorted(names))


def _extract_requirements(content: str) -> tuple[str, ...]:
    """Extract package names from requirements.txt-like content."""
    names = {
        name
        for line in content.splitlines()
        if (name := _parse_requirement_name(line)) is not None
    }
    return tuple(sorted(names))


def _project_name(
    files: dict[str, str],
    root_name: str,
) -> tuple[str, list[str]]:
    """Infer a project name from metadata or the supplied root name."""
    errors: list[str] = []
    content = files.get("pyproject.toml")

    if content is None:
        candidates = [
            value
            for path, value in files.items()
            if PurePosixPath(path).name == "pyproject.toml"
        ]
        content = candidates[0] if candidates else None

    if content is not None:
        try:
            data = tomllib.loads(content)
            project = data.get("project", {})
            name = project.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip(), errors

            poetry_name = data.get("tool", {}).get("poetry", {}).get("name")
            if isinstance(poetry_name, str) and poetry_name.strip():
                return poetry_name.strip(), errors
        except (tomllib.TOMLDecodeError, AttributeError) as exc:
            errors.append(f"pyproject.toml: {exc}")

    return root_name or "unknown-project", errors


def _json_dependencies(content: str) -> tuple[str, ...]:
    """Extract dependency names from package.json without executing anything."""
    data: Any = json.loads(content)
    if not isinstance(data, dict):
        return ()

    names: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        dependencies = data.get(section, {})
        if isinstance(dependencies, dict):
            names.update(
                name.lower().replace("_", "-").replace(".", "-")
                for name in dependencies
                if isinstance(name, str)
            )

    return tuple(sorted(names))


def analyze_repository(
    snapshot: RepoSnapshot,
    *,
    root_name: str = "",
) -> RepositoryAnalysis:
    """Analyze repository structure, metadata, dependencies, and Python code."""
    files = snapshot.files
    metadata_errors: list[str] = []

    project_name, name_errors = _project_name(files, root_name)
    metadata_errors.extend(name_errors)

    languages = {
        LANGUAGE_SUFFIXES[PurePosixPath(path).suffix.lower()]
        for path in files
        if PurePosixPath(path).suffix.lower() in LANGUAGE_SUFFIXES
    }

    directories: set[str] = set()
    for path in files:
        parts = PurePosixPath(path).parts
        for index in range(1, len(parts)):
            directories.add("/".join(parts[:index]) + "/")

    project_structure = tuple(sorted(directories | set(files)))

    entry_points = tuple(
        sorted(
            path
            for path in files
            if PurePosixPath(path).suffix.lower() == ".py"
            and PurePosixPath(path).name.lower() in ENTRY_POINT_NAMES
        )
    )

    config_files = tuple(
        sorted(path for path in files if PurePosixPath(path).name in CONFIG_NAMES)
    )

    dependencies: set[str] = set()

    for path, content in files.items():
        filename = PurePosixPath(path).name.lower()

        try:
            if filename == "requirements.txt":
                dependencies.update(_extract_requirements(content))
            elif filename == "pyproject.toml":
                dependencies.update(_extract_pyproject_dependencies(content))
            elif filename == "package.json":
                dependencies.update(_json_dependencies(content))
        except (
            tomllib.TOMLDecodeError,
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ) as exc:
            metadata_errors.append(f"{path}: {exc}")

    frameworks = {
        framework
        for dependency in dependencies
        if (framework := FRAMEWORK_DEPENDENCIES.get(dependency)) is not None
    }

    python_sources = {
        path: content for path, content in files.items() if path.lower().endswith(".py")
    }
    python_analysis = analyze_python_sources(python_sources)

    # Also inspect imports so frameworks can be detected when a manifest
    # is absent. This is a heuristic, not proof that a dependency is installed.
    import_to_framework = {
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django": "Django",
        "streamlit": "Streamlit",
        "gradio": "Gradio",
        "torch": "PyTorch",
        "tensorflow": "TensorFlow",
        "transformers": "Hugging Face Transformers",
        "langchain": "LangChain",
    }

    for file_result in python_analysis.files:
        if file_result.status != "parsed":
            continue

        for fact in file_result.imports:
            module = (fact.module or "").split(".", maxsplit=1)[0]
            imported_names = fact.names if fact.kind == "import" else (module,)
            for imported_name in imported_names:
                top_level = imported_name.split(".", maxsplit=1)[0]
                framework = import_to_framework.get(top_level)
                if framework:
                    frameworks.add(framework)

    return RepositoryAnalysis(
        project_name=project_name,
        languages=tuple(sorted(languages)),
        project_structure=project_structure,
        entry_points=entry_points,
        dependencies=tuple(sorted(dependencies)),
        frameworks=tuple(sorted(frameworks)),
        config_files=config_files,
        python_analysis=python_analysis,
        metadata_errors=tuple(sorted(metadata_errors)),
    )
