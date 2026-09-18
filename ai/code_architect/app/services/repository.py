from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.config import settings


TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".scss",
    ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".sql",
    ".java", ".go", ".rs", ".php", ".cs", ".sh", ".dockerfile",
}

IMPORTANT_FILENAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "package.json",
    "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle",
    "terraform.tf", "main.tf", "serverless.yml", "serverless.yaml",
    ".env.example", "readme.md",
}

IGNORED_PARTS = {
    ".git", "node_modules", "dist", "build", ".next", ".venv", "venv",
    "__pycache__", "coverage", ".idea", ".vscode",
}


@dataclass
class RepoSnapshot:
    file_tree: list[str]
    contents: dict[str, str]
    skipped: list[str]

    def to_prompt_text(self) -> str:
        sections = ["# FILE TREE", *self.file_tree, "", "# FILE CONTENTS"]
        for path, content in self.contents.items():
            sections.extend([f"\n## FILE: {path}", content])
        if self.skipped:
            sections.extend(["", "# SKIPPED FILES", *self.skipped])
        return "\n".join(sections)


def _safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return not (
        path.is_absolute()
        or ".." in path.parts
        or any(part in IGNORED_PARTS for part in path.parts)
    )


def _interesting(name: str) -> bool:
    path = PurePosixPath(name)
    lower_name = path.name.lower()
    return lower_name in IMPORTANT_FILENAMES or path.suffix.lower() in TEXT_EXTENSIONS


def read_zip_repository(data: bytes) -> RepoSnapshot:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("The uploaded file is not a valid ZIP archive.")

    tree: list[str] = []
    contents: dict[str, str] = {}
    skipped: list[str] = []
    total_chars = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        members.sort(key=lambda m: m.filename)

        for member in members:
            name = member.filename.replace("\\", "/")
            if not _safe_path(name):
                skipped.append(f"{name} (unsafe/ignored path)")
                continue

            tree.append(name)
            if len(contents) >= settings.max_files or not _interesting(name):
                continue

            # Avoid unexpectedly large files.
            if member.file_size > 2_000_000:
                skipped.append(f"{name} (too large)")
                continue

            raw = zf.read(member)
            if b"\x00" in raw[:4096]:
                skipped.append(f"{name} (binary)")
                continue

            text = raw.decode("utf-8", errors="replace")
            text = text[: settings.max_file_chars]

            remaining = settings.max_repo_chars - total_chars
            if remaining <= 0:
                skipped.append(f"{name} (repository text budget reached)")
                continue

            text = text[:remaining]
            contents[name] = text
            total_chars += len(text)

    if not tree:
        raise ValueError("The ZIP archive does not contain readable files.")

    return RepoSnapshot(file_tree=tree, contents=contents, skipped=skipped)
