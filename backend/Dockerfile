# syntax=docker/dockerfile:1.7
# Backend image. Stages:
#   base    - runtime dependencies and application code
#   test    - base + development tooling and tests
#   runtime - final image used by development and production (default target)
#   tofu-tools    - pinned OpenTofu + provider mirror/cache (depends only on provider pins)
#   deploy-runner - base + tofu-tools + the module library (ADR-026)

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
# The AI layer is a sibling package (ADR-009); only its source ships in the image.
COPY ai/src/cloudpilot_ai ./cloudpilot_ai
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


# OpenTofu and its providers, in a stage that depends only on the pinned provider versions, so
# application or module edits never re-download the (large) AWS provider.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS tofu-tools

# OpenTofu, pinned and checked against the release's published SHA-256.
ADD --checksum=sha256:40c9743977873a6d0ca4f273914588a20fb923c015deb6c4fe36f65575ee2b1c \
    https://github.com/opentofu/opentofu/releases/download/v1.10.9/tofu_1.10.9_linux_amd64.tar.gz \
    /tmp/tofu.tgz
RUN tar -xzf /tmp/tofu.tgz -C /usr/local/bin tofu && rm /tmp/tofu.tgz && tofu version

# A provider mirror plus an unpacked plugin cache that jobs link to: runs never reach a
# registry, and providers execute from the image because the job work dir is a noexec tmpfs.
# The lock file generated here ships with the stack, so the cache is used (not copied).
COPY docker/deploy-runner/tofurc /opt/tofu/tofurc
COPY infrastructure/opentofu/stacks/container-postgres/versions.tf /opt/tofu/pin/versions.tf
# hadolint ignore=DL3003
RUN mkdir -p /opt/tofu/plugin-cache \
    && cd /opt/tofu/pin \
    && tofu providers mirror -platform=linux_amd64 /opt/tofu/providers \
    && TF_CLI_CONFIG_FILE=/opt/tofu/tofurc TF_PLUGIN_CACHE_DIR=/opt/tofu/plugin-cache \
       tofu init -backend=false -input=false \
    && rm -rf .terraform


FROM base AS deploy-runner

COPY --from=tofu-tools /usr/local/bin/tofu /usr/local/bin/tofu
COPY --from=tofu-tools /opt/tofu /opt/tofu
# The fixed module library (read-only), with the provider lock file generated above.
COPY infrastructure/opentofu /opt/cloudpilot/opentofu
RUN cp /opt/tofu/pin/.terraform.lock.hcl /opt/cloudpilot/opentofu/stacks/container-postgres/

ENV TF_CLI_CONFIG_FILE=/opt/tofu/tofurc \
    TF_PLUGIN_CACHE_DIR=/opt/tofu/plugin-cache \
    CLOUDPILOT_STACKS_DIR=/opt/cloudpilot/opentofu/stacks \
    TF_IN_AUTOMATION=1 \
    CHECKPOINT_DISABLE=1 \
    HOME=/tmp \
    TMPDIR=/tmp

USER 10001
# One job per container lifetime; compose restarts it fresh for the next job.
CMD ["python", "-m", "app.deploy.runner", "--once"]


FROM base AS runtime

USER 10001
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
