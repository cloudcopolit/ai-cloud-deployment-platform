#!/bin/sh
# The full CloudPilot flow against REAL AWS, through the UI (frontend/e2e-real). Never run by
# scripts/e2e.sh or CI. It deploys into the sandbox account named in .env (CLOUDPILOT_AWS_*),
# then destroys everything it created and proves no tagged resource remains.
#
#   scripts/real-flow.sh            start/refresh the dev stack, run the flow, write evidence
#
# Evidence: test-runs/<YYYY-MM-DD>/run-<HHMMSS>/ (Africa/Cairo time; git-ignored because the
# screenshots show the account id and your IP): screenshots/, CHANGES.md, RESULT.md.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# Node on Windows needs a native path (Git Bash's /d/... would become D:\d\...)
ROOT_NATIVE=$(pwd -W 2>/dev/null || pwd)
export MSYS_NO_PATHCONV=1

STAMP=$(node -e '
const f = new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Cairo", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const p = Object.fromEntries(f.formatToParts(new Date()).map((x) => [x.type, x.value]));
console.log(`${p.year}-${p.month}-${p.day} ${p.hour}${p.minute}${p.second}`)')
DAY=${STAMP% *}
TIME=${STAMP#* }
RUN_DIR="test-runs/$DAY/run-$TIME"
mkdir -p "$RUN_DIR/screenshots"
echo "==> evidence folder: $RUN_DIR"

echo "==> AWS identity (sandbox guard)"
ACCOUNT=$(sh scripts/aws.sh sts get-caller-identity --query Account --output text | tr -d '\r')
echo "    account $ACCOUNT"

REPO="$ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/cloudpilot-examples/reference-app"
DIGEST=$(sh scripts/aws.sh ecr describe-images --repository-name cloudpilot-examples/reference-app \
    --image-ids imageTag=v1 --query "imageDetails[0].imageDigest" --output text | tr -d '\r')
IMAGE_URI="$REPO@$DIGEST"
echo "    image $IMAGE_URI"

node scripts/real-flow-report.mjs changes "$RUN_DIR"

echo "==> dev stack (backend, worker, deploy runner, egress proxy, dev mirror, frontend)"
docker compose up -d --build --wait

echo "==> the flow, in a real browser"
status=0
(cd frontend && RUN_DIR="$ROOT_NATIVE/$RUN_DIR" IMAGE_URI="$IMAGE_URI" AWS_SANDBOX_ACCOUNT_ID="$ACCOUNT" \
    pnpm exec playwright test -c playwright.real.config.ts) || status=$?

echo "==> evidence (CloudTrail, cost, RESULT.md)"
node scripts/real-flow-report.mjs result "$RUN_DIR" "$status" || true
git rev-parse HEAD > test-runs/.last-run-sha
echo "==> done: $RUN_DIR (flow exit $status)"
exit $status
