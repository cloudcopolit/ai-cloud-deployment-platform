# CloudPilot · RUNBOOK

How to run, operate and recover CloudPilot locally and against a sandbox AWS account.
For the big picture read `PLANNING.md`; for evidence per session read `WORKLOG.md`.

## 1. Prerequisites

- Docker Desktop (Compose v2), Node 22 + pnpm (only for the browser tests), Git Bash on Windows.
- `.env` from `.env.example` (git-ignored). Secrets live only there and in `secrets/` (git-ignored,
  docker-ignored). Never paste values into chat, issues or logs.

| Variable | Needed for |
|---|---|
| `CLOUDPILOT_AWS_ACCESS_KEY_ID`, `CLOUDPILOT_AWS_SECRET_ACCESS_KEY`, `CLOUDPILOT_AWS_REGION` | CloudPilot's own AWS identity (assumes customer roles). Empty = deployments disabled. |
| `ARCHITECT_AUTOMATED_ARCHETYPES=true` | priced, deployable architecture plans (off = prototype template only) |
| `GITHUB_DEV_MIRROR_URL=http://github-dev-mirror:8080` | dev only: analyze `examples/*` as `cloudpilot-examples/*` |
| `GITHUB_TOKEN` / GitHub App variables | more GitHub quota, private repositories |
| `ANTHROPIC_API_KEY` etc. | optional language-model step (MOCKED-ONLY without keys) |

## 2. Start, stop, reset

```sh
docker compose up -d --build --wait   # db, localstack, backend, worker, deploy-runner,
                                      # egress-proxy, github-dev-mirror, frontend
docker compose ps
docker compose logs -f backend worker deploy-runner
docker compose down                   # keep data
docker compose down --volumes         # wipe the dev database
```

UI: http://localhost:3000 · API: http://localhost:8000 (OpenAPI at `/docs`).
Dev sign-in (only when `DEV_LOGIN_ENABLED=true`): Alice (OWNER), Bob (ADMIN), Carol (MEMBER).

## 3. Quality gates

```sh
scripts/check.sh            # backend + ai + frontend (lint, types, tests, coverage, build)
scripts/e2e.sh              # isolated browser suite: fake GitHub, throwaway DB, ports 3100/8100
node frontend/scripts/contrast.mjs
```

`scripts/e2e.sh` never touches real GitHub or AWS. The real-AWS flow is separate (section 6).

CI (`.github/workflows/`) runs on every pull request, stacked ones included: backend lint/types/tests
and a **migrations** job (one head, upgrade, `alembic check`, append-only audit trigger, downgrade and
back), AI, frontend (with contrast), **End-to-end** (`scripts/e2e.sh` unchanged), infrastructure
(OpenTofu fmt/validate, TFLint, Hadolint, Compose, Trivy, the deploy-runner image offline, the egress
allowlist) and security (Gitleaks, pip/pnpm audit, **Semgrep**). CodeQL is not available on this
private Free-plan repository (GitHub answers 403), so Semgrep is the SAST step. Accepted findings
are inline `trivy:ignore` / `nosemgrep` comments with the reason and ADR.

## 4. Connect an AWS account (once per account)

1. UI → **AWS accounts** → connect the 12-digit account id (ADMIN/OWNER).
2. **Download onboarding template** and deploy it in that account, e.g.
   ```sh
   scripts/aws.sh cloudformation deploy --region us-east-1 \
     --stack-name <stack shown in the UI> --template-file /work/<path to the json> \
     --capabilities CAPABILITY_NAMED_IAM
   ```
   It creates the deploy role (trusted only by CloudPilot's principal with this account's External
   ID), its permission boundary, and the encrypted state bucket.
3. **Verify connection**: a real STS AssumeRole with the External ID; the card must show
   "AssumeRole without the External ID is denied".

## 5. Deploy, approve, destroy

1. Architecture page (automated plan) → **Deploy this architecture**.
2. Image pinned by digest (`…@sha256:…`), allowed CIDR (**Use my IP**) → **Create the OpenTofu plan**.
3. Review resources, cost and policy checks → tick the review box → **Approve plan** (binds to the plan's SHA-256).
4. **Apply this plan to AWS** → watch steps; RDS takes several minutes.
5. Health check passed → live URL (reachable only from the allowed CIDR, HTTP).
6. **Destroy deployment** (type `destroy`) → wait for "Destroyed" and the zero-resource proof.

## 6. The real-AWS end-to-end run

```sh
scripts/real-flow.sh
```

Starts or refreshes the dev stack, drives the whole flow in a browser against the sandbox account,
destroys everything, and writes `test-runs/<date>/run-<time>/` (git-ignored): `screenshots/`,
`CHANGES.md`, `RESULT.md` (steps with durations, health output, zero-resource check, CloudTrail
session names, cost). The test image is `cloudpilot-examples/reference-app:v1` in the account's ECR;
rebuild and push it with:

```sh
REPO=<account>.dkr.ecr.us-east-1.amazonaws.com/cloudpilot-examples/reference-app
docker build --platform linux/amd64 -t $REPO:v1 examples/reference-app
scripts/aws.sh ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${REPO%%/*}
docker push $REPO:v1
```

## 7. When something goes wrong

| Symptom | What to do |
|---|---|
| Deployment stuck in PLANNING/APPLYING | `docker compose logs deploy-runner`. A runner silent for `DEPLOY_RUNNER_STALE_AFTER_S` (300 s) is swept to `TIMED_OUT`; destroy is then offered. |
| `FAILED` · `APPLY_FAILED` | The page lists resources that exist; fix the cause, then **Destroy** (never re-apply blindly). |
| `FAILED` · `HEALTH_CHECK_FAILED` | Infrastructure is still running. Check the log group `/cloudpilot/<deployment-id>`; destroy or fix the image. |
| `DESTROY_FAILED` | Retry destroy. If tagged resources remain, list them: `scripts/aws.sh resourcegroupstaggingapi get-resources --tag-filters Key=cloudpilot:deployment-id,Values=<id>`. |
| State lock held after a crash | The lock file is `deployments/<id>/terraform.tfstate.tflock` in the state bucket; remove it only after confirming no runner is working on that deployment. |
| Verification fails | Re-deploy the onboarding template; the External ID shown in the UI must match the trust policy. |
| Network flakes pushing images | Re-run `docker push` (layers resume). |
| `real-flow.sh` stops before the browser ("the dev stack did not start") | A registry or npm download timed out. The script already retried the build three times and wrote `RESULT.md`; run it again. |
| Frontend build fails at `ls -d node_modules/.pnpm/@next+swc-*` | pnpm skipped Next's native compiler after a failed download; rebuild (`docker compose build frontend`). Without this guard the image hung at start-up. |
| "… is already connected to this project" for `cloudpilot-examples/*` | The dev mirror is serving old code; `docker compose restart github-dev-mirror` (`real-flow.sh` does this). |
| Destroy shows "Destroying" for minutes after OpenTofu finished | The tagging index lags behind deletions. The check confirms each listed resource with its own service and reports it as "indexed but gone"; wait for "Destroyed". |

## 8. Cleanup of everything a sandbox test created

- Deployments: destroy from the UI (tag `cloudpilot:deployment-id`).
- Onboarding: `scripts/aws.sh cloudformation delete-stack --stack-name <stack>`; the state bucket is
  retained by design (delete its objects and the bucket manually if wanted).
- Test image: `scripts/aws.sh ecr delete-repository --repository-name cloudpilot-examples/reference-app --force`.
