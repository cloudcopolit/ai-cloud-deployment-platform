from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import RepositoryRef
from AI.domain.aws_detection.models import AwsConfigKind, AwsConfigStatus
from AI.domain.shared.errors import RepositoryAccessError

# Bounds keep GitHub API usage and scan time predictable.
MAX_FILES_SCANNED = 150
MAX_CHARS_PER_FILE = 60_000
DEFAULT_CONCURRENCY = 8

_SKIP_DIR_PARTS = frozenset(
    {
        "node_modules",
        "vendor",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".next",
        "site-packages",
    }
)
_SKIP_NAMES = frozenset(
    {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "go.sum"}
)
_SCAN_SUFFIXES = frozenset(
    {
        ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml",
        ".toml", ".tf", ".txt", ".cfg", ".ini", ".sh", ".env", ".go", ".java", ".rb", ".php",
    }
)
_PRIORITY_NAMES = frozenset(
    {
        "cdk.json", "serverless.yml", "serverless.yaml", "samconfig.toml", "samconfig.yaml",
        "samconfig.yml", "template.yml", "template.yaml", "requirements.txt", "pyproject.toml",
        "Pipfile", "package.json", "go.mod", "pom.xml", "build.gradle", "Gemfile", "composer.json",
    }
)
_IAC_PATH_NAMES = frozenset(
    {"cdk.json", "serverless.yml", "serverless.yaml", "samconfig.toml", "samconfig.yaml", "samconfig.yml"}
)

# --- Detection patterns. Only the *kind* and file path are kept, never matched text. ---
_IAC_CONTENT = re.compile(
    r"AWSTemplateFormatVersion|AWS::Serverless|AWS::[A-Z][A-Za-z0-9]+::[A-Z]"
    r"|provider\s+\"aws\"|resource\s+\"aws_|aws-cdk-lib|\baws_cdk\b"
)
_SDK_CONTENT = re.compile(r"\b(?:boto3|botocore|aioboto3|aiobotocore)\b|@aws-sdk/|\baws-sdk\b")
_CREDENTIAL_REF = re.compile(
    r"\b(?:AWS_PROFILE|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)\b"
)
_REGION = re.compile(
    r"\b(?:AWS_REGION|AWS_DEFAULT_REGION)\b"
    r"|\bregion_name\s*="
    r"|\bregion\s*[:=]\s*[\"']?[a-z]{2}(?:-[a-z]+)+-\d\b"
    r"|\bRegion\s*:\s*[a-z]{2}(?:-[a-z]+)+-\d\b"
)
_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_SECRET_ASSIGN = re.compile(
    r"(?i)aws_?secret_?access_?key[\"']?\s*[:=]\s*[\"']([A-Za-z0-9/+=]{40})[\"']"
)


def _is_scannable(path: str) -> bool:
    p = PurePosixPath(path)
    if p.name in _SKIP_NAMES or any(part in _SKIP_DIR_PARTS for part in p.parts[:-1]):
        return False
    return (
        p.suffix.lower() in _SCAN_SUFFIXES
        or p.name.startswith(".env")
        or p.name == "Procfile"
        or p.name.startswith("Dockerfile")
    )


def _priority(path: str) -> int:
    p = PurePosixPath(path)
    if p.name in _PRIORITY_NAMES:
        return 0
    if p.name.startswith(("Dockerfile", ".env")) or ".github/workflows/" in path:
        return 1
    return 2 + len(p.parts)


def _has_hardcoded_credentials(text: str) -> bool:
    for match in _ACCESS_KEY.finditer(text):
        if "EXAMPLE" not in match.group(0):
            return True
    for match in _SECRET_ASSIGN.finditer(text):
        if "EXAMPLE" not in match.group(0):
            return True
    return False


def classify_file(path: str, text: str) -> frozenset[AwsConfigKind]:
    """Pure function: which AWS config kinds does this one file show?"""
    kinds: set[AwsConfigKind] = set()
    if PurePosixPath(path).name in _IAC_PATH_NAMES or _IAC_CONTENT.search(text):
        kinds.add(AwsConfigKind.IAC_TEMPLATE)
    if _SDK_CONTENT.search(text):
        kinds.add(AwsConfigKind.SDK_CLIENT)
    if _CREDENTIAL_REF.search(text):
        kinds.add(AwsConfigKind.CREDENTIALS_REFERENCE)
    if _REGION.search(text):
        kinds.add(AwsConfigKind.REGION_SETTING)
    if _has_hardcoded_credentials(text):
        kinds.add(AwsConfigKind.HARDCODED_CREDENTIALS)
    return frozenset(kinds)


def _build_status(kinds: tuple[AwsConfigKind, ...]) -> AwsConfigStatus:
    # ASSUMPTION: AwsConfigStatus takes the detected kinds as `kinds=`.
    # This is the only line that touches its constructor; adjust here if yours differs.
    return AwsConfigStatus(kinds=kinds)


@dataclass(frozen=True)
class AwsConfigScan:
    """Immutable scan result. Holds paths only, never file content or secret values."""

    status: AwsConfigStatus
    findings: tuple[tuple[AwsConfigKind, tuple[str, ...]], ...] = ()
    files_scanned: int = 0

    def files_for(self, kind: AwsConfigKind) -> tuple[str, ...]:
        for found_kind, files in self.findings:
            if found_kind is kind:
                return files
        return ()


class AwsConfigScanner:
    """Deterministic (no LLM) scan for AWS configuration signals at a pinned commit.

    Results are memoised per RepositoryRef (repo + commit_sha) so the use case and the
    agent can both ask without a second GitHub fetch.
    """

    def __init__(
        self,
        reader: RepositoryReader,
        access_token: str = "",
        *,
        max_files: int = MAX_FILES_SCANNED,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._reader = reader
        self._access_token = access_token
        self._max_files = max_files
        self._concurrency = max(1, concurrency)
        self._cache: dict[RepositoryRef, AwsConfigScan] = {}

    async def scan(self, repo: RepositoryRef) -> AwsConfigScan:
        cached = self._cache.get(repo)
        if cached is not None:
            return cached

        all_files = await self._reader.list_files(repo, self._access_token)
        candidates = sorted(
            (f for f in all_files if _is_scannable(f)),
            key=lambda p: (_priority(p), p),
        )[: self._max_files]

        semaphore = asyncio.Semaphore(self._concurrency)

        async def inspect(path: str) -> tuple[str, frozenset[AwsConfigKind]]:
            async with semaphore:
                try:
                    text = await self._reader.read_file(repo, path, self._access_token)
                except RepositoryAccessError:
                    return path, frozenset()
            return path, classify_file(path, text[:MAX_CHARS_PER_FILE])

        results = await asyncio.gather(*(inspect(p) for p in candidates))

        by_kind: dict[AwsConfigKind, list[str]] = {}
        for path, kinds in results:
            for kind in sorted(kinds, key=lambda k: k.value):
                by_kind.setdefault(kind, []).append(path)

        ordered_kinds = tuple(sorted(by_kind, key=lambda k: k.value))
        scan = AwsConfigScan(
            status=_build_status(ordered_kinds),
            findings=tuple((k, tuple(by_kind[k])) for k in ordered_kinds),
            files_scanned=len(candidates),
        )
        self._cache[repo] = scan
        return scan
