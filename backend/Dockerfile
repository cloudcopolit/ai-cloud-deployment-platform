# Backend image. Stages:
#   base    - runtime dependencies and application code
#   test    - base + development tooling and tests
#   runtime - final image used by development and production (default target)

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY ai ./ai
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000


FROM base AS test

COPY backend/requirements-dev.txt backend/pyproject.toml ./
RUN pip install -r requirements-dev.txt
COPY backend/tests ./tests
COPY ruff.toml /app/ruff.toml

# /app is read-only for the app user; keep coverage data and caches in /tmp.
ENV COVERAGE_FILE=/tmp/.coverage
USER 10001
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider", "--cov"]


FROM base AS runtime

USER 10001
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
