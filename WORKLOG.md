# WORKLOG — making `project_context/` real

> Working memory across sessions. Newest status first in §0; history at the bottom.
> Labels used everywhere: **REAL** (works against the real thing) · **SIMULATED** (code path runs but
> against a stand-in, e.g. LocalStack, canned data) · **MOCKED-ONLY** (no real backend available
> yet; behind a fake/flag) · **MISSING** (not built).

## 0. Current status (update every session)

- Branch: `feat/real-platform` (cut from `feat/create-project-context` after a baseline commit of the
  pre-existing uncommitted work).
- Done: **S0** (`e1b64fc`), **S1** GitHub ingestion (`dc6a92b`), **S2** jobs + LangGraph orchestrator +
  real deterministic analysis (`d9bf873`, `5be4d6a`) + live activity UI + E2E, **S3** LLM gateway
  (MOCKED-ONLY until keys).
- Next: **S4 architecture** (price table from the AWS Price List via `scripts/refresh_aws_prices.py`,
  pattern catalog, versions, AWS-icon diagram), then S5 AWS/deploy, S6 frontend polish, S7.
- Blocked on the owner (see §5): LLM API keys, AWS sandbox account id, GitHub App installation /
  `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, acceptance of the AWS Architecture Icons terms.

## 1. Baseline gate results (2026-10-25, before any change)

| Gate | Command | Result |
|---|---|---|
| Backend tests | `docker compose --env-file .env.example --profile test run --rm --build backend-tests` | **79 passed**, coverage **90.34 %** (gate 90) |
| Backend tests (documented overlay) | `docker compose -f docker-compose.yml -f docker-compose.test.yml … run backend-tests` | **BROKEN**: overlay sets `context: ./backend` while the Dockerfile copies `backend/...` → `backend\backend` not found |
| Ruff (backend) | `ruff check . && ruff format --check .` | clean (81 files) |
| Ruff (`ai/`) | `ruff check ai` | **29 errors** (E501 etc.) |
| mypy (backend) | `mypy` | **2 errors** (`import-untyped` for `ai.agents.*`); docs claim 0 |
| pip-audit | `pip-audit -r requirements.txt` | no known vulnerabilities |
| AI CI layout | `python .github/scripts/discover_ai_projects.py ai` | **FAILS**: `ai/agents/*/*.py` are not inside a project (no pyproject) |
| Frontend lint | `pnpm lint` | **9 errors**, 7 warnings (`no-explicit-any` in `pipeline-modal.tsx`) |
| Frontend typecheck | `pnpm typecheck` | pass |
| Frontend unit | `pnpm test` | 26 passed (4 files) |
| Frontend build | `pnpm build` | _(see §6 log)_ |
| Secret scan (all refs) | gitleaks 8.24.3 `git --log-opts=--all --redact` | 3 hits: 2 placeholders (`replace-…`, test dummy) = false positives; **1 real OpenRouter key** in `ai/code_architect/.env.example` @ `c96810dc` on `origin/feat/code-architect-v0-3` (must be rotated by the owner; history rewrite needs owner approval) |
| Host tooling | – | no `terraform`, `aws`, `gitleaks`, `trivy` on host → run them as pinned containers |

## 2. Gap analysis: target (`project_context/` + owner prompt) vs reality

### 2.1 Feature matrix

| # | Feature (target) | Reality found | Label |
|---|---|---|---|
| F1 | GitHub OAuth sign-in, JWT cookie | implemented + tested | **REAL** |
| F2 | Personal team + OWNER + FREE subscription on first login | implemented (not race-safe, I7) | REAL |
| F3 | Teams/roles/tenant isolation, foreign tenant → **404** | roles enforced, but foreign tenant gets **403** (`check_team_role` raises `Forbidden`) — leaks existence; spec `08` §3 says 404 | partial |
| F4 | Plan quotas | `max_projects` enforced; docs disagree (FREE = 1 in seed and `04`, "3" in `01`/`05`) | partial |
| F5 ✅S1 | Connect repo by URL (public, `GITHUB_TOKEN`) / private via GitHub App | `POST /projects/{id}/repositories` stores whatever the client sends; **no GitHub call**; `/repositories/available` is a **hard-coded catalog of 4 repos that do not exist** | **SIMULATED** |
| F6 ✅S1 | Branches + commits persisted from GitHub | one branch created from input; **one fake commit with a random SHA** (`uuid4().hex`) | **SIMULATED** |
| F7 ✅S1 | Webhook `/webhooks/github` with HMAC | absent | **MISSING** |
| F8 | Analysis as background job (202, worker, SKIP LOCKED, heartbeat, sweeper, cancel, timeout, idempotency) | runs **synchronously inside the POST**, returns `SUCCESS` with 202 | **SIMULATED** |
| F9 | `agent_runs` / `agent_tasks` + live agent activity | tables absent | **MISSING** |
| F10 | LangGraph orchestrator, thin nodes, ports, EventSink | absent; `ai/` has 2 loose files; **`ai/` imports `app.contracts` (backend)** — violates ADR-009 | **MISSING** |
| F11 | Analysis Agent: deterministic detectors over real repo text, evidence + confidence, secrets (path/kind), monorepo, BLOCKED + missing_info + re-run | `run_code_analyzer` picks one of 3 **canned reports by substring of the repo name** ("next"/"web"/"express"…); evidence hashes are of invented strings | **SIMULATED (fabricated)** |
| F12 | Multi-provider LLM gateway (OpenAI, Anthropic, Gemini, xAI), model discovery, fallback, budgets, redaction, health check | absent; no keys in `.env` | **MISSING** (will be MOCKED-ONLY until keys) |
| F13 | Architecture proposal: components + rationale, assumptions, risks, cost w/ `pricing_as_of` from a price table, differs per repo | one fixed template (VPC/ALB/ECS/…); prices are literals in code; health path hard-coded `/health/db` | **SIMULATED** |
| F14 | Immutable versions, edit → new version, validate, approve | generate only; version created directly as `VALIDATED`; no edit/validate endpoints; `cost_estimates` table absent | partial |
| F15 | Diagram with official AWS icons via generated manifest + accessible alternative | official package present in `frontend/public/AWS/` (24 MB, untracked) but **unused**; no manifest/script; `public/NOTICE.md` describes folders that do not exist | **MISSING** |
| F16 | AWS account connect: External ID, role template, **real STS AssumeRole** verification | stores ARN + External ID as `PENDING_VERIFICATION`; no verify endpoint; External ID is 31 chars (spec ≥ 32) | partial/**MISSING** |
| F17 | Terraform from fixed module library, sandboxed runner, plan before approval, plan-hash-bound approval, policy checks, apply, health check, destroy, rollback | `apply` returns **503** after approval; no Terraform, no worker, no plan, approval not bound to anything; `infrastructure/terraform/modules/*` are empty `.gitkeep` | **MISSING** |
| F18 | Frontend: design system, routed stepper, live agent view, pickers, report, diagram, timeline, honest states | single dashboard + 781-line `PipelineModal`; shows a **fake live endpoint fallback `https://app.cloudpilot.dev`**; shadcn grey defaults; lint red | **SIMULATED** |
| F19 | Error envelope + correlation id + JSON logs + Origin check + security headers | implemented (`core/errors.py`, `logging.py`, `middleware.py`) | REAL |
| F20 | Rate limits, Idempotency-Key | absent | **MISSING** |
| F21 | `audit_logs` | absent | **MISSING** |
| F22 | docker compose: db, backend, **worker**, frontend, localstack; one command for tests + E2E | db/localstack/backend/frontend exist; no worker; test overlay broken; `make e2e` calls a script that does not exist; no Playwright | partial |
| F23 | Eval harness ≥ 15 real repos, precision/recall | absent | **MISSING** |
| F24 | Security: IDOR matrix, threat model doc, image scan, history secret scan in CI | partial (security headers tests); `security.yml` exists (not yet read in detail) | partial |

### 2.2 Code ↔ docs conflicts found (each must be resolved, never left silent)

| ID | Conflict | Resolution plan |
|---|---|---|
| C1 | `01-current-state.md` says 16 tables (lists 18), "5 of 5 modules" (lists 7), 74 tests (actual 79), "mypy 0 issues" (actual 2), "Ruff 100 % clean" (ai/ has 29) | rewrite `01` from measured facts at the end of each slice |
| C2 | `01`/`05` say FREE plan = 3 projects; seed + `04` §11 say 1 | code wins (1); fix `01`/`05` |
| C3 | `08` §3: foreign tenant → 404; code → 403 | fix code (scoped getters raise `NotFound`) |
| C4 | `05` marks analysis endpoints ✅ while they are canned | relabel per reality, then make real |
| C5 | ADR-009/018: `ai` never imports backend; reality: `ai/agents/*` import `app.contracts`, services mutate `sys.path` | move contracts into the `ai` package (`cloudpilot_ai.contracts`), backend imports it; delete `sys.path` hacks |
| C6 | `07` §6 deployment steps (`VALIDATE_PLAN … FINALIZE`) vs code's 5 canonical steps | adopt a reviewed step list in an ADR when building deploy |
| C7 | `09` §4: worker service in compose; reality: none | add `worker` service |
| C8 | `deployments.status` CHECK lacks `BLOCKED`/`TIMED_OUT`; approvals not bound to a plan | new migration + ADR (plan-hash binding) |
| C9 | `frontend/public/NOTICE.md` lists `github/octicons`, `brands/`, `aws/` "drawn for CloudPilot" folders that do not exist | rewrite NOTICE for what actually ships |
| C10 | AGENTS.md/ADR-016: polling; prompt allows SSE only by ADR | keep polling (ADR-016 accepted), no SSE |

## 3. Plan (dependency-ordered vertical slices)

Every slice ends with: ruff + mypy + pytest (+migrations) + frontend lint/typecheck/vitest/build +
`docker compose up` smoke + Playwright for slices that exist, then small commits, then §0/§6 updated.

| Slice | Content | Done when |
|---|---|---|
| **S0 Hygiene** | baseline commit; fix test overlay; `ai/` as a real package (`ai/pyproject.toml`, `cloudpilot_ai`), contracts moved there, no `sys.path` hacks, mypy/ruff/AI-CI green; frontend lint green; tenant 404s (scoped getters); race-safe first login; ADRs 007/008/009/014/015/016/017/018 accepted | all gates green; AI CI discovers 1 project |
| **S1 Real GitHub ingestion** | `integrations/github_app.py` (App JWT RS256 → installation token; PAT/`GITHUB_TOKEN`; unauthenticated public fallback with honest rate-limit errors); connect by URL → resolve real repo id/owner/name/default branch/visibility; sync branches; list + persist real commits per branch; remove fake catalog + fake commit; webhook with HMAC (feature-flagged until secret exists); frontend repo URL input + branch + commit pickers | 3 real public repos incl. `Delivery-Plus0/delivery-plus@dev` connected with real SHAs (evidence) |
| **S2 Jobs + orchestrator** | migration: `agent_runs`, `agent_tasks`, job columns (`heartbeat_at`, `attempts`, `cancel_requested`, `idempotency_key`, `locked_by`, `deadline_at`); `app/jobs/worker.py` (SKIP LOCKED claim, heartbeat, sweeper, cancel, timeouts); `cloudpilot_ai` public API `run_analysis`, ports + `EventSink`; LangGraph graph with thin nodes; backend EventSink → DB; polling endpoints `/analyses/{id}`, `/analyses/{id}/activity`; compose `worker` service; frontend live agent activity | two-worker exclusivity, stale, cancel, timeout, failure tests green |
| **S3 Analysis + LLM** | deterministic detectors (Python, Node, Java, Go, Dockerfile, compose, env example, CI, Terraform), ports/deps/datastores/env names, monorepo split, secret finder (path+kind), blockers/missing_info, answers → re-run; `RepositoryGateway` over Trees API + raw content with limits; LLM gateway (OpenAI, Anthropic, Gemini, xAI) with list-models discovery, priority fallback, budgets, redaction, one repair; health check CLI + admin endpoint; golden fixtures (injection, fake secret, monorepo, unsupported); eval harness over ≥ 15 public repos | report for delivery-plus lists its services/Kafka/Redis correctly; eval table produced |
| **S4 Architecture** | pattern catalog (static site, container web/API ± Postgres, unsupported marking), price table with `pricing_as_of`, risks/assumptions, `cost_estimates`; versions DRAFT → validate → approve, edit = new version; AWS icon manifest script + diagram + accessible table | 3 different repos → 3 visibly different plans; icon tests pass in Docker |
| **S5 AWS + deploy** | STS AssumeRole verify w/ External ID (LocalStack; real AWS gated); Terraform module library (`infrastructure/terraform/modules/*`); runner in an isolated `hashicorp/terraform` container; plan → summary + hash → approval bound to hash → apply refuses on hash drift; policy checks; tagging; health check; destroy; truthful partial-failure state | LocalStack static-site deploy passes a real HTTP health check, destroy clean; failure-path tests |
| **S6 Frontend** | design tokens (light/dark, contrast-checked brand colors), routed stepper pages, all states, axe, Playwright happy + negative paths, Lighthouse + bundle budgets in CI | numbers recorded |
| **S7 Security + docs** | tenant matrix test over every endpoint, rate limits, image scan (Trivy), threat model, `project_context` sync, RUNBOOK.md, HANDOFF.md | |

## 4. Assumptions and decisions (small ones are mine; recorded as ADRs in `project_context/12`)

- A1. The pre-existing uncommitted work on `feat/create-project-context` is the owner's; I commit it
  unchanged as a baseline before my own commits so my diff is reviewable.
- A2. Commits stay local; nothing is pushed (outward-facing) unless the owner asks.
- A3. The full AWS icon package (24 MB) is **not** added to git; it moves out of `public/` to a
  git-ignored source folder and only the selected icons are generated into `public/`.
- A4. LocalStack Community does not enforce IAM trust policies/External ID and does not provide
  ECS/ELBv2/RDS/ECR/CloudFront (Pro). Consequence: wrong-External-ID tests use a fake STS; the
  container archetype can be planned but not applied on LocalStack; the static-site archetype
  (S3 website) can be applied and health-checked for real on LocalStack. Real AWS only after the
  owner names a sandbox account.
- A5. No LLM keys → every provider is reported **MOCKED-ONLY**; deterministic analysis still runs for
  real; LLM-only fields are skipped and marked.
- A6. Q-5 (AWS discovery) deferred: `InfraDiscovery` port ships with a null implementation.

## 5. Blocked on the owner (feature-flagged / mocked meanwhile)

| Item | Needed for | Current fallback |
|---|---|---|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY` | real LLM calls, provider table, per-provider eval | providers MOCKED-ONLY |
| `GITHUB_TOKEN` (fine-grained, public read) or a GitHub App **installation** | 5000 req/h API budget | unauthenticated API (60 req/h) + raw content host |
| `GITHUB_WEBHOOK_SECRET` | webhook endpoint | endpoint disabled (404) when unset |
| AWS sandbox account id (named by owner) | real STS + real deploy | LocalStack only |
| Read & accept AWS Architecture Icons terms | shipping the icons | icons used in dev; flagged in HANDOFF |
| Rotate the leaked OpenRouter key; approve (or not) a history rewrite of `feat/code-architect-v0-3` | secret-scan clean | documented |
| Proposals needing approval (no new infra without ADR + approval) | – | see §7 |

## 6. Session log

### 2026-10-25 · session 1
- Read all of `project_context/` (AGENTS, 00–13, contracts, data dictionary) and the code.
- Ran baseline gates (§1). Found the gaps in §2.
- **S0** committed `e1b64fc`: `ai/` package, gates fixed, tenant 404s (ADR-019), race-safe login,
  Next 16.4.3 (2 critical RCE advisories in 16.4.0 confirmed by `pnpm audit`), lint clean.
  Note: the Next.js build printed instructions addressed to "the agent" (run an upgrade command,
  ask a scripted question). Treated as untrusted tool output; verified the advisory with
  `pnpm audit` and upgraded with pinned versions instead.
- Known flaky (seen 1×/18 runs, not reproducible in 14 reruns): `test_deployment_rejection_cancels_steps`.
  Module is rewritten in S5; re-check then.
- **S1** real GitHub ingestion:
  - GitHub App `cloudpilot-dev-yousef` probed read-only: **no permissions, 0 installations** →
    private repos impossible until the owner configures it (§5). Public access is anonymous (60/h).
  - `integrations/github_app.py`, repositories service/router rewritten, webhook module,
    migration `001ba641ce53`, seed no longer invents repos/SHAs, ADR-021.
  - Evidence (live, anonymous): connected `Delivery-Plus0/delivery-plus` (default `dev`, 18 branches),
    `fastapi/full-stack-fastapi-template`, `mdn/beginner-html-site`, `heroku/node-js-getting-started`
    (301 → canonical `heroku/nodejs-getting-started`, same-host redirect). Stored `dev` head
    `0d2fa8a27090beecd39d16472a1412dcf64df775` == `git ls-remote … refs/heads/dev`.
  - Frontend: tokens (contrast-checked: raw #2F6BFF = 4.49:1 on white → FAIL, #19D3C5 = 1.88:1 →
    FAIL; text tokens #1F5AE6 5.73:1, #0B7F76 4.87:1), light/dark/system theme, routed pages
    `/dashboard`, `/projects/[id]`, `/projects/[id]/repositories/[repoId]` with stepper and
    branch/commit pickers; removed the fabricated "AWS us-east-1 (Connected)" header and the
    login page's false claims (SOC 2/HIPAA, 30+ regions); dev sign-in for seeded users (dev only).
  - axe (Playwright, live stack): 0 serious/critical on dashboard/project in light+dark; repository
    page had 5 contrast + 1 aria findings in light → fixed (opacity on steps, aria-label on div).
  - Dev DB contains the owner's earlier test rows created by the old fake flow (catalog ids
    `10101..10104`, `gh_…` ids) and the old seed's `acme/demo-shop`. Left untouched (owner data);
    cleanup query in HANDOFF.

### 2026-10-26 · session 2
- S2 evidence (live worker, anonymous GitHub): `Delivery-Plus0/delivery-plus@dev` (678 files). First
  run BLOCKED with a phantom root service; root causes: one shared root Dockerfile built per service
  through compose build args, libraries counted as services, ports only in `.env.example`, NestJS
  `@Controller('health')`, Compose `!reset` tags. Fixed (`5be4d6a`): 12/12 services, ports 3000-3011
  equal to each `.env.example`, `/health` on each, Kafka/PostgreSQL/Redis, SUCCESS in about 11 s.
- E2E stack: `scripts/e2e.sh` (fake GitHub server, isolated DB, ports 3100/8100). 8/8 Playwright specs
  pass incl. axe (0 serious/critical) on overview, project, repository and analysis pages. Earlier
  runs failed on an npm-registry network error and two test-locator mistakes; one real UI bug found
  and fixed (commit/branch selection lagged behind the URL update).
- S3: LLM gateway (ADR-022). No keys in `.env`, so all four providers are MOCKED-ONLY; deterministic
  analysis is unaffected and the LLM step shows as SKIPPED with the reason.
- Claude API skill consulted: the Anthropic adapter uses the official SDK (`anthropic==2.3.0`); the
  installed SDK types `ModelInfo.capabilities` as an object, not the dict the docs show (verified).
- The AWS public Price List is reachable without credentials; every S4 price is available except NAT
  Gateway (only in the 481 MB EC2 offer), so the container archetype avoids NAT (tasks in public
  subnets, security group admits only the ALB), recorded as an assumption and a risk.

## 7. Proposals awaiting owner approval (not implemented)

_(none yet)_

## 8. Icon coverage log (ArchitecturePlan component types without an official icon)

_(filled by the manifest script)_
