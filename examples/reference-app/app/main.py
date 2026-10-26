"""CloudPilot reference app: a tiny notes API on PostgreSQL.

Reads its database from DATABASE_URL, or from DB_HOST / DB_PORT / DB_NAME / DB_USER /
DB_PASSWORD. GET /health checks the database with a real query.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

STARTED = time.time()


def _conninfo() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return psycopg.conninfo.make_conninfo(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "app"),
        user=os.environ.get("DB_USER", "app"),
        password=os.environ.get("DB_PASSWORD", ""),
        connect_timeout=5,
    )


@contextmanager
def db() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_conninfo(), autocommit=True) as conn:
        yield conn


app = FastAPI(title="CloudPilot reference app")


@app.on_event("startup")
def create_schema() -> None:
    # The database may still be starting; retry for a minute before giving up.
    for _ in range(30):
        try:
            with db() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS notes ("
                    "id serial PRIMARY KEY, body text NOT NULL, created_at timestamptz DEFAULT now())"
                )
            return
        except psycopg.OperationalError:
            time.sleep(2)


@app.get("/health")
def health() -> dict[str, object]:
    try:
        with db() as conn:
            version = conn.execute("SELECT version()").fetchone()
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail="database unreachable") from exc
    return {
        "status": "ok",
        "database": "ok",
        "postgres": (version[0] if version else "?").split(" on ")[0],
        "uptime_s": round(time.time() - STARTED, 1),
    }


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=500)


@app.get("/")
def index() -> dict[str, str]:
    return {"app": "cloudpilot-reference-app", "health": "/health", "notes": "/notes"}


@app.get("/notes")
def list_notes() -> list[dict[str, object]]:
    with db() as conn:
        rows = conn.execute("SELECT id, body, created_at FROM notes ORDER BY id DESC LIMIT 50")
        return [{"id": r[0], "body": r[1], "created_at": r[2].isoformat()} for r in rows]


@app.post("/notes", status_code=201)
def add_note(note: NoteIn) -> dict[str, object]:
    with db() as conn:
        row = conn.execute("INSERT INTO notes (body) VALUES (%s) RETURNING id", (note.body,)).fetchone()
    return {"id": row[0] if row else None, "body": note.body}
