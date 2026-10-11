from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from workflows.repository import RepoSnapshot, read_zip_repository


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_reads_supported_files_without_extracting():
    archive = make_zip(
        {
            "project/app.py": b"print('hello')",
            "project/pyproject.toml": b"[project]\nname='demo'",
            "project/image.png": b"\x89PNG",
        }
    )

    snapshot = read_zip_repository(archive)

    assert isinstance(snapshot, RepoSnapshot)
    assert snapshot.files == {
        "project/app.py": "print('hello')",
        "project/pyproject.toml": "[project]\nname='demo'",
    }
    assert snapshot.skipped_files == ("project/image.png",)


def test_rejects_path_traversal():
    archive = make_zip({"../outside.py": b"print('unsafe')"})

    with pytest.raises(ValueError, match="Unsafe ZIP path"):
        read_zip_repository(archive)


def test_rejects_too_many_entries():
    archive = make_zip({"one.py": b"1", "two.py": b"2"})

    with pytest.raises(ValueError, match="too many entries"):
        read_zip_repository(archive, max_files=1)


def test_rejects_oversized_file():
    archive = make_zip({"app.py": b"x" * 20})

    with pytest.raises(ValueError, match="size limit"):
        read_zip_repository(archive, max_file_size=10)


def test_rejects_invalid_zip():
    with pytest.raises(ValueError, match="Invalid ZIP archive"):
        read_zip_repository(b"not a zip archive")


def test_skips_non_utf8_supported_file():
    archive = make_zip({"data.json": b"\xff\xfe"})

    snapshot = read_zip_repository(archive)

    assert snapshot.files == {}
    assert snapshot.skipped_files == ("data.json",)
