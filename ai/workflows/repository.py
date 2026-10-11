"""Safe ingestion of ZIP repositories for CloudPilot workflows."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

SUPPORTED_SUFFIXES = {".py", ".toml", ".txt", ".yaml", ".yml", ".json"}
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_FILE_SIZE = 1_000_000
DEFAULT_MAX_TOTAL_SIZE = 20_000_000
DEFAULT_MAX_ARCHIVE_SIZE = 25_000_000


@dataclass(frozen=True, slots=True)
class RepoSnapshot:
    """A validated, in-memory snapshot of supported repository files."""

    files: dict[str, str]
    skipped_files: tuple[str, ...] = ()


def _safe_member_path(name: str) -> str | None:
    """Return a normalized safe relative path, or None for unsafe entries."""
    if not name or "\x00" in name or "\\" in name:
        return None

    path = PurePosixPath(name)

    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None

    if path.parts and ":" in path.parts[0]:
        return None

    return path.as_posix()


def read_zip_repository(
    archive_bytes: bytes,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
    max_archive_size: int = DEFAULT_MAX_ARCHIVE_SIZE,
) -> RepoSnapshot:
    """Read supported text files without extracting or executing uploaded code."""
    if not isinstance(archive_bytes, bytes):
        raise TypeError("archive_bytes must be bytes")

    if max_files < 1 or max_file_size < 1 or max_total_size < 1:
        raise ValueError("Resource limits must be positive")
    if max_archive_size < 1:
        raise ValueError("max_archive_size must be positive")
    if len(archive_bytes) > max_archive_size:
        raise ValueError("ZIP archive exceeds the maximum allowed size")

    try:
        archive = ZipFile(BytesIO(archive_bytes))
    except (BadZipFile, OSError) as exc:
        raise ValueError("Invalid ZIP archive") from exc

    files: dict[str, str] = {}
    skipped: list[str] = []
    total_size = 0

    with archive:
        entries = archive.infolist()

        if len(entries) > max_files:
            raise ValueError("ZIP contains too many entries")

        seen_paths: set[str] = set()

        for entry in entries:
            if entry.is_dir():
                continue

            safe_path = _safe_member_path(entry.filename)
            if safe_path is None:
                raise ValueError(f"Unsafe ZIP path: {entry.filename!r}")

            if safe_path in seen_paths:
                raise ValueError(f"Duplicate ZIP path: {safe_path!r}")
            seen_paths.add(safe_path)

            # Reject symbolic links and other non-regular Unix file entries.
            unix_mode = (entry.external_attr >> 16) & 0xFFFF
            file_type = unix_mode & 0o170000
            if file_type not in (0, 0o100000):
                raise ValueError(f"Unsupported ZIP entry type: {safe_path!r}")

            if entry.flag_bits & 0x1:
                raise ValueError(
                    f"Encrypted ZIP entries are unsupported: {safe_path!r}"
                )

            if entry.file_size > max_file_size:
                raise ValueError(f"ZIP entry exceeds size limit: {safe_path!r}")

            total_size += entry.file_size
            if total_size > max_total_size:
                raise ValueError("ZIP contents exceed the total size limit")

            suffix = PurePosixPath(safe_path).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                skipped.append(safe_path)
                continue

            try:
                raw = archive.read(entry)
                text = raw.decode("utf-8")
            except (BadZipFile, OSError, RuntimeError) as exc:
                raise ValueError(f"Could not read ZIP entry: {safe_path!r}") from exc
            except UnicodeDecodeError:
                skipped.append(safe_path)
                continue

            files[safe_path] = text

    return RepoSnapshot(
        files=dict(sorted(files.items())),
        skipped_files=tuple(sorted(skipped)),
    )
