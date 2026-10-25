# 12 · Architecture Decision Records

> Status: **Accepted** = already in code or in the README/AI brief (team intent) · **Proposed** = 💡 recommended here, **needs team agreement** · **Superseded** = replaced.
> To add an ADR: copy the template, take the next number, link it from the file it affects.

## Index

| ADR | Title | Status |
|---|---|---|
| 001 | Modular monolith (FastAPI + feature modules) | Accepted |
| 002 | PostgreSQL only for the MVP; no queue / object store yet | Accepted |
| 003 | JWT in HttpOnly cookie, roles read from DB per request | Accepted |
| 004 | GitHub OAuth for identity; GitHub App for repository access | Accepted |
| 005 | `VARCHAR`+`CHECK` instead of enums; `ON DELETE RESTRICT`; archive not delete | Accepted |
| 006 | JSONB for AI documents, normalize only what is queried | Accepted |
| 007 | Add `BLOCKED`, `TIMED_OUT`, `CANCELLED` job statuses | Accepted |
| 008 | DB-backed job queue (`FOR UPDATE SKIP LOCKED`) | Proposed |
| 009 | AI layer as an in-process sibling package behind a narrow interface | Accepted |
| 010 | Two IAM roles per customer account: read-only and deploy | Proposed |
| 011 | Generalize `approvals` to deployments | Proposed |
| 012 | Break the `agent_runs` ↔ `deployments`/`incidents` FK cycle across migrations | Proposed |
| 013 | Terraform state lives in the customer's own S3 bucket | Proposed |
| 014 | LangGraph for orchestration with thin nodes | Proposed (AI brief: "consider") |
| 015 | Deterministic-first analysis, LLM only for ambiguity | Proposed |
| 016 | Polling for job status (SSE later) | Proposed |
| 017 | Domain exceptions in services + one error envelope | Proposed |
| 018 | Shared `contracts` package consumed by backend and AI layer | Accepted (variant, see text) |
| 019 | Foreign tenant → 404, insufficient role → 403 | Accepted |
| 020 | Official AWS icon package kept out of git, `public/` and images; generated subset only | Accepted |
| 021 | Repository access resolution (App → token → anonymous); connect by URL; repos per project | Accepted |

---

## ADR-001 · Modular monolith — Accepted
**Context.** Small team, graduation timeline, one database.
**Decision.** One FastAPI app, feature modules with `router → service → models` layering; modules call each other only through services.
**Consequences.** Simple deploy and transactions. Boundaries must be policed (import rules in `03` §1). A module can later be extracted because it already owns its tables.

## ADR-002 · PostgreSQL only for the MVP — Accepted
**Context.** AI brief: "standard PostgreSQL is sufficient; job queues or object storage can be introduced later".
**Decision.** Jobs, results, history, audit in PostgreSQL. Time-series stays out (Prometheus). Large artifacts in JSONB until size demands S3.
**Consequences.** One system to operate. Revisit when job volume or payload size hurts (`02` §6).

## ADR-003 · JWT cookie, roles from DB — Accepted
**Decision.** HS256 JWT with `sub/iat/exp` only, HttpOnly cookie (+ Bearer for tools); team roles are **not** in the token.
**Consequences.** Role changes apply immediately (one extra query). No refresh token: 30-min re-login (I11). Needs Origin check for CSRF (I6).

## ADR-004 · OAuth for identity, GitHub App for repo access — Accepted
**Decision.** OAuth scope `read:user user:email` only. Repository contents via a GitHub App installation with read-only permissions and short-lived tokens.
**Consequences.** Least privilege, per-repo consent, webhooks for commits. Requires App registration and key management.

## ADR-005 · `VARCHAR`+`CHECK`, `RESTRICT`, archive — Accepted
**Decision.** No native PG enums; all FKs `ON DELETE RESTRICT`; projects are archived.
**Consequences.** Easy Alembic changes; history safe. Deleting a team/user for privacy needs an explicit anonymization procedure (see `04` §10).

## ADR-006 · JSONB for AI documents — Accepted
**Decision.** `analysis_data`, `architecture_data`, `breakdown` are JSONB validated by Pydantic before write; `services` normalized because it is filtered/joined.
**Consequences.** Schema evolves without migrations; carry `schema_version`; promote a field to a column when you query it.

## ADR-007 · New job statuses — Accepted (2026-10-25: in `repository_analyses` CHECK since migration `9f907e2152cb`)
**Context.** ERD has `QUEUED/RUNNING/SUCCESS/FAILED`; the brief saves a *blocked* outcome; timeouts are first-class.
**Decision.** Allow `QUEUED, RUNNING, SUCCESS, BLOCKED, FAILED, TIMED_OUT, CANCELLED` on `repository_analyses` and `agent_runs`.
**Consequences.** `BLOCKED` is **not** a failure (system worked, repo not deployable yet). Frontend must render it differently. Terminal states list is used by polling (`05` §4).

## ADR-008 · DB-backed queue — Proposed
**Decision.** Worker claims `QUEUED` rows with `FOR UPDATE SKIP LOCKED`, sets `RUNNING`, heartbeats; a sweeper times out or re-queues stale jobs.
**Alternatives.** Celery/Arq/RQ + Redis (more infra), SQS (AWS lock-in, cost). **Swap path** keeps API and tables unchanged.
**Consequences.** Polling load on PG is negligible at MVP scale; needs `created_at` + `(status, created_at)` index (P3).

## ADR-009 · AI layer as in-process sibling package — Accepted (2026-10-25, closes Q-1)
**Decision.** `ai/` package with a public API `run_analysis(AnalysisRequest) -> AgentResult[AnalysisReport]`; the backend worker imports it. Same contracts allow an HTTP service later.
**Alternatives.** Separate microservice now (network, auth, deploy overhead for no benefit).
**Consequences.** One deployable for the demo; strict import direction (`ai` never imports `backend`); the backend provides the persistence hook, the AI layer stays stateless (`06` §7).
**As built.** Package `cloudpilot_ai` in `ai/src/` with `ai/pyproject.toml` (one AI CI project). The backend image copies `ai/src/cloudpilot_ai` next to `app/`; backend pytest/mypy put `../ai/src` on the path. The former `sys.path` manipulation in backend services was removed.

## ADR-010 · Two IAM roles — Proposed
**Decision.** `cloudpilot-readonly` for discovery/planning, `cloudpilot-deploy` for apply; separate ARNs on `aws_accounts`; deploy role assumed only by the deployment worker after an approval.
**Consequences.** Enforces the planning/deploy boundary in AWS, not just in code. Customer setup is slightly longer (one template creating both).

## ADR-011 · Generalize `approvals` — Proposed
**Decision.** Add nullable `deployment_id`; `CHECK (num_nonnulls(healing_action_id, deployment_id) = 1)`; unique per subject.
**Consequences.** One approval mechanism for "controlled deployment with approval" (README Phase 2) and healing (Phase 3). Alternative (separate `deployment_approvals`) duplicates logic.

## ADR-012 · Break the FK cycle — Proposed
**Context.** `agent_runs` needs `deployments`/`incidents`, which come later; `healing_actions` points back to `agent_runs`; analysis needs `agent_runs` first.
**Decision.** M3 creates `agent_runs` with `deployment_id`/`incident_id` as plain nullable UUIDs; M5 and M7 add the FK constraints.
**Consequences.** Unblocks the AI work early; each migration stays valid on its own.

## ADR-013 · Terraform state in customer's S3 — Proposed
**Decision.** Generated Terraform configures an S3 backend (+ DynamoDB or S3 native locking) in the customer's account; CloudPilot stores only plan summaries and resource inventory.
**Consequences.** No state (which contains secrets) in our DB; customer keeps control and can leave. Needs a bootstrap step creating the bucket.

## ADR-014 · LangGraph orchestration — Proposed
**Decision.** Orchestrator is a LangGraph `StateGraph` with typed state, conditional edges (blocked vs ok), parallel fan-out (repo ‖ infra), per-node timeout/retry. Nodes only call the Communication Module and update state. LangChain only where it saves real time.
**Consequences.** Visible workflow, easy to test paths with fakes. Pin the version; keep a thin adapter so the graph could be replaced.
**Milestone.** Ship analysis-only graph first, add architect nodes after (`06` §3.4).

## ADR-015 · Deterministic-first analysis — Proposed
**Decision.** Parse manifests/Dockerfiles/CI with real parsers; use the LLM only for ambiguous judgments on small redacted excerpts.
**Consequences.** Cheaper, reproducible, testable, harder to prompt-inject. More code up front.

## ADR-016 · Polling for status — Proposed
**Decision.** `POST` → 202 + id; clients poll `GET` every 1–2 s with back-off until a terminal state. SSE/WebSocket later if needed.
**Consequences.** Matches the brief ("request job status → read persisted results"), trivial to implement and cache.

## ADR-017 · Domain exceptions + error envelope — Proposed
**Decision.** Services raise `NotFound/Forbidden/Conflict/QuotaExceeded/UpstreamError`; one handler maps to the envelope (`05` §1) with `correlation_id`.
**Consequences.** Services are HTTP-free and testable; the AI layer's `ErrorInfo.code` maps 1:1.

## ADR-018 · Shared contracts package — Accepted, variant (2026-10-25)
**Decision.** `contracts/ai_contracts.py` becomes an installable package imported by backend and AI layer; JSON Schema exported for the frontend.
**Consequences.** One definition; version it (`schema_version`) and run contract tests in both CI pipelines.
**Variant adopted.** Instead of a third package, the contracts live in `cloudpilot_ai.contracts` (owned by the AI layer, imported by the backend). That keeps the import direction of ADR-009 with one less package to install. `project_context/contracts/ai_contracts.py` stays as the reviewed v1.0 draft; the code module is authoritative and changes there must update the draft and `ai-contracts.md`.

## ADR-019 · Foreign tenant → 404, insufficient role → 403 — Accepted (2026-10-25)
**Context.** `08` §3 requires 404 for other teams' objects (no existence leak); the code returned 403 from `check_team_role` for non-members.
**Decision.** `check_team_role` raises `NotFound` when the caller is not a member of the owning team and `Forbidden` only when the member's role is too low.
**Consequences.** IDOR probes cannot distinguish "exists in another team" from "does not exist". Tests for outsiders assert 404.

## ADR-020 · AWS Architecture Icons handling — Accepted (2026-10-25)
**Context.** The official package (release `07312026`, ≈24 MB, mixed-case folder names) was dropped into `frontend/public/AWS/`, which ships whole in the frontend image and is served as-is; Linux paths are case-sensitive.
**Decision.** The package moves to `frontend/vendor/aws-icons/` (git-ignored, docker-ignored). `scripts/build-aws-icon-manifest.mjs` copies only the icons the diagram uses, **unmodified**, into `frontend/public/aws-icons/` with lowercase file names and writes a typed manifest (`src/lib/aws-icons/manifest.ts`). The original package is never committed unless the owner approves.
**Consequences.** Small, reviewable, case-safe asset set; the AWS icon terms must be accepted by the owner (HANDOFF.md).

## ADR-021 · Repository access resolution — Accepted (2026-10-25, closes Q-3)
**Context.** The previous connect endpoint stored whatever ids/names the client sent and invented a commit with a random SHA. The GitHub App (ADR-004) is registered but has no permissions or installations yet, and public repositories must work without it.
**Decision.**
1. `POST /projects/{id}/repositories` takes only `{url}`. Everything else (numeric id, canonical owner/name, default branch, visibility) comes from GitHub; branches and recent commits are mirrored. No SHA is ever generated by CloudPilot.
2. Per request, credentials are resolved most-privileged first: GitHub App installation token (minted with an RS256 App JWT, cached until shortly before expiry; "not installed" cached 5 min) → `GITHUB_TOKEN` → anonymous. The mode used is stored on `repositories.access_mode` with `is_private` and `last_synced_at` (migration `001ba641ce53`).
3. Public file contents are read from the raw content host (no API quota); App-mode reads use the contents API. Only full 40-character SHAs are accepted for trees/files; symlinks and submodules are skipped; per-file byte limits apply; redirects (renamed repositories) are followed only on the same host.
4. Q-3: the same GitHub repository may be connected to several projects (`UNIQUE(project_id, github_repository_id)`); webhooks fan out to every project that has the pushed branch as its deployment branch.
5. Webhooks are HMAC-verified (`X-Hub-Signature-256`), idempotent on `(repository_id, sha)`, disabled (404) until `GITHUB_WEBHOOK_SECRET` is set, and never deploy (Q-11 default).
**Consequences.** Real data only; anonymous mode is limited to 60 API requests/hour, so the UI reads cached commits first. Private repositories need the owner to grant the App `Contents: read` + `Metadata: read` and install it.

---

## Template

```
## ADR-0NN · Title — Proposed | Accepted | Superseded by ADR-0MM
**Context.** What forces the decision?
**Decision.** What we will do.
**Alternatives.** What else we considered and why not.
**Consequences.** What gets easier/harder; follow-ups.
```
