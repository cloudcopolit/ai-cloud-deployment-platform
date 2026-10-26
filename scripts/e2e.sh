#!/bin/sh
# End-to-end suite: builds and starts an isolated stack (fake GitHub, throwaway database,
# ports 3100/8100), runs Playwright against it, and always tears it down.
#
#   scripts/e2e.sh            run every spec
#   scripts/e2e.sh --keep     leave the stack running afterwards (for debugging)
#   scripts/e2e.sh -g blocked any extra arguments go to `playwright test`
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

KEEP=false
if [ "${1:-}" = "--keep" ]; then
    KEEP=true
    shift
fi

E2E="docker compose -p cloudpilot-e2e -f docker-compose.yml -f docker-compose.e2e.yml --env-file .env.example"

cleanup() {
    if [ "$KEEP" = false ]; then
        echo "==> tearing down the e2e stack"
        $E2E down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

echo "==> starting the e2e stack (fake GitHub, isolated database)"
$E2E up -d --build --wait db fake-github backend worker frontend

echo "==> running Playwright"
cd frontend
E2E_BASE_URL=http://localhost:3100 E2E_API_URL=http://localhost:8100 pnpm exec playwright test "$@"
