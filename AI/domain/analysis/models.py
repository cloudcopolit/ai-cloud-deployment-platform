from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    name: str
    commit_sha: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class LanguageStat:
    name: str
    bytes_of_code: int


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str  # "npm", "pip", "maven", ...
    version: str | None = None


@dataclass(frozen=True)
class AnalysisReport:
    repo: RepositoryRef
    languages: tuple[LanguageStat, ...]
    frameworks: tuple[str, ...]
    dependencies: tuple[Dependency, ...]
    entry_points: tuple[str, ...]
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))