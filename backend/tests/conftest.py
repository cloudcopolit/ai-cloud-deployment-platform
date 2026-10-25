"""Shared test configuration.

Settings are forced here, before any `app` module is imported, so values in a
developer's `.env` can never point the tests at a real database or real
GitHub credentials. Database tests run against TEST_DATABASE_URL, whose
database name must end in `_test`.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_test_db_url() -> str:
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                u = make_url(val)
                db_name = u.database or "cloudpilot"
                test_db = db_name if db_name.endswith("_test") else f"{db_name}_test"
                return u.set(database=test_db).render_as_string(hide_password=False)
    return "postgresql+psycopg://cloudpilot:cloudpilot@172.23.9.99:5432/cloudpilot_test"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _default_test_db_url()


if not (make_url(TEST_DATABASE_URL).database or "").endswith("_test"):
    raise RuntimeError(
        "TEST_DATABASE_URL must name a dedicated database ending in '_test'; "
        "the test suite creates, rolls back, and drops data in it."
    )

os.environ.update(
    {
        "DATABASE_URL": TEST_DATABASE_URL,
        "ENVIRONMENT": "development",
        "JWT_SECRET_KEY": "test-only-jwt-secret-0123456789abcdefghijklmnopqrstuvwxyz",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "FRONTEND_URL": "http://localhost:3000",
        "GITHUB_CLIENT_ID": "test-client-id",
        "GITHUB_CLIENT_SECRET": "test-client-secret",
        "GITHUB_REDIRECT_URI": "http://localhost:8000/auth/github/callback",
    }
)

# Imported after the environment is configured; app.core.config reads it at import time.
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import engine, get_db  # noqa: E402
from app.integrations.github_app import get_github_client  # noqa: E402
from app.main import app  # noqa: E402
from tests.fakes import FakeGitHub  # noqa: E402


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_engine(alembic_config: Config) -> Engine:
    """Bring the test database to the latest migration once per session."""
    command.upgrade(alembic_config, "head")
    return engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session whose work, including commits, is rolled back after each test."""
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def fake_github() -> Iterator[FakeGitHub]:
    """Every test gets an empty in-memory GitHub, so no test can reach the real one.
    Tests that need repositories add them: ``fake_github.add_repo("o", "r")``."""
    fake = FakeGitHub()
    github_client = fake.client()
    app.dependency_overrides[get_github_client] = lambda: github_client
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_github_client, None)
        github_client.close()
