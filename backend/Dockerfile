# Backend image. Stages:
#   base    - runtime dependencies and application code
#   test    - base + development tooling and tests (docker-compose.test.yml)
#   runtime - final image used by development and production (default target)

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000


FROM base AS test

COPY requirements-dev.txt pyproject.toml ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests

# /app is read-only for the app user; keep coverage data and caches in /tmp.
ENV COVERAGE_FILE=/tmp/.coverage
USER 10001
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider", "--cov"]


FROM base AS runtime

USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
