#!/bin/sh
# CloudPilot quality gates. Runs every check in containers so results match CI.
#
#   scripts/check.sh            all gates (backend, ai, frontend)
#   scripts/check.sh backend    ruff + mypy + pytest --cov (90 % gate) incl. migration tests
#   scripts/check.sh ai         ruff + mypy + pytest for ai/ and the CI project-discovery check
#   scripts/check.sh frontend   lint + typecheck + vitest + production build (host pnpm)
#
# Exits non-zero on the first failing gate.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# Git Bash on Windows rewrites /repo-style arguments; keep them as written.
export MSYS_NO_PATHCONV=1

TEST_COMPOSE="docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.example"
TOOLS_IMAGE=cloudpilot-test-backend-tests

tools() {
    docker run --rm -u 0 -e HOME=/tmp -e RUFF_CACHE_DIR=/tmp/ruff -v "$ROOT:/repo" \
        --entrypoint sh "$TOOLS_IMAGE" -c "$1"
}

build_tools() {
    echo "==> building the backend test image"
    $TEST_COMPOSE build -q backend-tests
}

check_lint() {
    echo "==> ruff (backend + ai)"
    tools "cd /repo && ruff check backend ai && ruff format --check backend ai"
}

check_backend() {
    build_tools
    check_lint
    echo "==> mypy (backend)"
    tools "cd /repo/backend && mypy"
    echo "==> pytest (backend, real PostgreSQL in an isolated compose project)"
    status=0
    $TEST_COMPOSE run --rm backend-tests || status=$?
    $TEST_COMPOSE down --volumes >/dev/null 2>&1 || true
    return $status
}

check_ai() {
    build_tools
    echo "==> mypy + pytest (ai)"
    tools "cd /repo/ai && mypy . && python -m pytest -q -p no:cacheprovider -m 'not live_llm'"
    echo "==> AI CI project discovery"
    python3 .github/scripts/discover_ai_projects.py ai >/dev/null 2>&1 \
        || python .github/scripts/discover_ai_projects.py ai >/dev/null
}

check_frontend() {
    echo "==> frontend: install, lint, typecheck, unit tests, build"
    (cd frontend && pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck && pnpm test && pnpm build)
}

case "${1:-all}" in
    backend) check_backend ;;
    ai) check_ai ;;
    frontend) check_frontend ;;
    lint) build_tools && check_lint ;;
    all) check_backend && check_ai && check_frontend ;;
    *) echo "usage: $0 [all|backend|ai|frontend|lint]" >&2; exit 2 ;;
esac
echo "==> all requested gates passed"
