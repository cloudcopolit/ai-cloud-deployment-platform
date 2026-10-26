"""Bounded, read-only view of one repository commit (06 §4.2 steps B-D).

Files are fetched as bytes and decoded as text. Nothing is executed, imported or evaluated.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field

from cloudpilot_ai.analysis.files import (
    LANGUAGE_BY_EXT,
    READ_PRIORITY,
    Kind,
    classify,
    is_skipped,
)
from cloudpilot_ai.contracts import ErrorCode, Stage
from cloudpilot_ai.errors import AgentError, Budget
from cloudpilot_ai.ports import RepositoryGateway

MAX_FILE_BYTES = 256_000
MAX_SOURCE_FILES = 200  # source files sampled for env-var, port and route references
# file names that usually carry ports, env reads, routes or the start-up code
SIGNAL_NAME = re.compile(
    r"(?i)^(main|server|app|index|config|settings|application|bootstrap|routes?|urls|"
    r"[\w.-]*(config|health|status|probe)[\w.-]*)\.(py|[cm]?[jt]sx?|go|java|kt|rb|php|rs)$"
)
READ_WORKERS = 8


@dataclass
class Snapshot:
    files: dict[str, str]  # path -> decoded text of every file that was read
    kinds: dict[str, Kind]  # path -> kind, for every listed (non-skipped) file
    hashes: dict[str, str]  # path -> sha256 of the bytes that were read
    language_bytes: Counter[str] = field(default_factory=Counter)
    listed: int = 0
    skipped: int = 0  # listed but not read (generated, binary, over budget)
    truncated: bool = False  # listing incomplete or a limit was hit
    unreadable: list[str] = field(default_factory=list)

    def of_kind(self, *kinds: Kind) -> list[str]:
        return sorted(p for p, k in self.kinds.items() if k in kinds and p in self.files)

    def exists(self, path: str) -> bool:
        return path in self.kinds

    def sha(self, path: str) -> str:
        return self.hashes.get(path) or hashlib.sha256(path.encode()).hexdigest()


def _decode(data: bytes) -> str | None:
    if b"\x00" in data[:4096]:
        return None  # binary content behind a text-looking name
    return data.decode("utf-8", errors="replace")


def take_snapshot(
    repository: RepositoryGateway,
    *,
    budget: Budget,
    max_files: int,
    max_total_bytes: int,
) -> Snapshot:
    listing = repository.list_files()
    kinds: dict[str, Kind] = {}
    language_bytes: Counter[str] = Counter()
    skipped = 0
    for entry in listing.entries:
        path = entry.path
        if path.startswith("/") or ".." in path.split("/"):
            skipped += 1
            continue
        if is_skipped(path):
            skipped += 1
            continue
        kind = classify(path)
        kinds[path] = kind
        language = LANGUAGE_BY_EXT.get(posixpath.splitext(path)[1].lower())
        if language:
            language_bytes[language] += entry.size

    sizes = {e.path: e.size for e in listing.entries}
    candidates = [
        p for p, k in kinds.items() if k in READ_PRIORITY and sizes.get(p, 0) <= MAX_FILE_BYTES
    ]
    # Source files: likely config / entry / health files first, then shallow and small.
    sources = sorted(
        (p for p in candidates if kinds[p] is Kind.SOURCE),
        key=lambda p: (not SIGNAL_NAME.search(p.rsplit("/", 1)[-1]), p.count("/"), sizes.get(p, 0)),
    )[:MAX_SOURCE_FILES]
    chosen = [p for p in candidates if kinds[p] is not Kind.SOURCE] + sources
    chosen.sort(key=lambda p: (READ_PRIORITY[kinds[p]], p.count("/"), p))

    truncated = listing.truncated
    selected: list[str] = []
    total = 0
    for path in chosen:
        if len(selected) >= max_files or total + sizes.get(path, 0) > max_total_bytes:
            truncated = True
            break
        selected.append(path)
        total += sizes.get(path, 0)

    files: dict[str, str] = {}
    hashes: dict[str, str] = {}
    unreadable: list[str] = []

    def read(path: str) -> tuple[str, bytes | None]:
        budget.check(Stage.FETCH_REPOSITORY)
        try:
            return path, repository.read_file(path, MAX_FILE_BYTES)
        except AgentError as exc:
            if exc.info.code in {ErrorCode.GITHUB_RATE_LIMITED, ErrorCode.GITHUB_UNAUTHORIZED}:
                raise
            return path, None
        except Exception:  # one unreadable file must not sink the analysis
            return path, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=READ_WORKERS) as pool:
        for path, data in pool.map(read, selected):
            text = _decode(data) if data is not None else None
            if text is None:
                unreadable.append(path)
                continue
            files[path] = text
            hashes[path] = hashlib.sha256(data or b"").hexdigest()

    return Snapshot(
        files=files,
        kinds=kinds,
        hashes=hashes,
        language_bytes=language_bytes,
        listed=len(listing.entries),
        skipped=skipped + (len(kinds) - len(files)),
        truncated=truncated,
        unreadable=unreadable,
    )
