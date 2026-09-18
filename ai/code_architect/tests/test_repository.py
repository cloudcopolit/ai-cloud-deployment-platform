import io
import zipfile

from app.services.repository import read_zip_repository


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_reads_text_repository():
    data = make_zip({
        "package.json": '{"dependencies":{"express":"1"}}',
        "src/index.js": "import express from 'express';",
        "node_modules/x.js": "ignored",
    })
    snapshot = read_zip_repository(data)
    assert "package.json" in snapshot.contents
    assert "src/index.js" in snapshot.contents
    assert "node_modules/x.js" not in snapshot.contents


def test_rejects_non_zip():
    try:
        read_zip_repository(b"hello")
        assert False, "Expected ValueError"
    except ValueError:
        pass
