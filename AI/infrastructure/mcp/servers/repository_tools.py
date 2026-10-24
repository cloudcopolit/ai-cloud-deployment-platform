from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from langchain_core.tools import StructuredTool, tool

from AI.application.analysis.redactor import (
    DEFAULT_MAX_CHARS,
    format_with_line_numbers,
    redact_secrets,
)
from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import RepositoryRef

SIGNAL_FILENAMES = {
    "Dockerfile",
    "Containerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "Procfile",
    "Makefile",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "tsconfig.json",
    "alembic.ini",
    "serverless.yml",
    "cdk.json",
}


def is_signal_file(path: str) -> bool:
    p = PurePosixPath(path)
    if p.name in SIGNAL_FILENAMES or p.name.startswith("Dockerfile.") or p.name.startswith(".env"):
        return True
    if ".github/workflows/" in path and p.suffix in {".yml", ".yaml"}:
        return True
    return False


@dataclass(frozen=True)
class RepositoryToolset:
    """Safe, redacted repository inspection tools scoped to a single RepositoryRef."""

    reader: RepositoryReader
    repo: RepositoryRef
    access_token: str = ""
    max_chars_per_file: int = DEFAULT_MAX_CHARS

    async def list_repo_files(self) -> str:
        """List all file paths in the repository and highlight key signal files."""
        files = await self.reader.list_files(self.repo, self.access_token)
        if not files:
            return "Repository is empty."
        signal_files = [f for f in files if is_signal_file(f)]
        lines = [
            f"Repository: {self.repo.full_name}@{self.repo.commit_sha}",
            f"Total files: {len(files)}",
            "Signal files detected:",
        ]
        if signal_files:
            lines.extend(f"  - {sf}" for sf in signal_files)
        else:
            lines.append("  (none)")
        lines.append("\nAll files:")
        lines.extend(f"  {f}" for f in files[:500])
        if len(files) > 500:
            lines.append(f"  ... ({len(files) - 500} more files)")
        return "\n".join(lines)

    async def read_repo_file(self, path: str) -> str:
        """Read a file from the repository with 1-based line numbers and secret redaction."""
        clean_path = path.strip().lstrip("/")
        files = await self.reader.list_files(self.repo, self.access_token)
        if clean_path not in files:
            return f"ERROR: File '{clean_path}' does not exist in {self.repo.full_name}@{self.repo.commit_sha}."

        raw = await self.reader.read_file(self.repo, clean_path, self.access_token)
        numbered = format_with_line_numbers(
            raw, path=clean_path, max_chars=self.max_chars_per_file
        )
        return f"=== File: {clean_path} ===\n{numbered}"

    async def search_repo_files(self, query: str) -> str:
        """Search for a case-insensitive substring across repository files and return matching lines."""
        q = query.strip()
        if not q:
            return "ERROR: Search query must not be empty."

        files = await self.reader.list_files(self.repo, self.access_token)
        matches: list[str] = []
        q_lower = q.lower()

        for file_path in files[:200]:
            raw = await self.reader.read_file(self.repo, file_path, self.access_token)
            safe_text = redact_secrets(raw[: self.max_chars_per_file], path=file_path)
            for idx, line in enumerate(safe_text.splitlines(), start=1):
                if q_lower in line.lower():
                    matches.append(f"{file_path}:{idx}: {line.strip()[:200]}")
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break

        if not matches:
            return f"No matches found for '{q}'."
        return "\n".join(matches)

    def as_langchain_tools(self) -> list[StructuredTool]:
        """Return LangChain StructuredTools ready to bind to a LangGraph ReAct agent."""

        @tool("list_repo_files")
        async def _list_repo_files() -> str:
            """List all file paths in the repository and identify key signal files (Dockerfile, manifests, configs)."""
            return await self.list_repo_files()

        @tool("read_repo_file")
        async def _read_repo_file(path: str) -> str:
            """Read a repository file at `path`. Returns 1-based line numbers for Evidence citations and redacts secrets."""
            return await self.read_repo_file(path)

        @tool("search_repo_files")
        async def _search_repo_files(query: str) -> str:
            """Search repository files for `query` (e.g. 'PORT', 'listen', 'health', 'FastAPI') with file and line numbers."""
            return await self.search_repo_files(query)

        return [_list_repo_files, _read_repo_file, _search_repo_files]  # type: ignore[list-item]
