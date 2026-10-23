# 05 · API Specification

> ✅ = implemented today (6 endpoints) · 📋💡 = **proposed design** for the remaining modules. Proposed paths are a starting point for the backend/frontend teams to agree on; nothing marked 💡 exists in code.
> Interactive docs for what exists: `http://localhost:8000/docs`.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000` (dev). Production: `api.<domain>` sharing a parent domain with the frontend (cookie must not be third-party) |
| Auth | `access_token` **HttpOnly cookie** (browser) or `Authorization: Bearer <jwt>` (Swagger/tools). Frontend must use `credentials: "include"`. `401` ⇒ not logged in |
| Content type | JSON (`application/json`) |
| IDs | UUID strings |
| Timestamps | ISO‑8601 UTC |
| Pagination 💡 | `?limit=20&offset=0` (max 100) → `{ "items": [...], "total": n, "limit": 20, "offset": 0 }` |
| Errors 💡 | one envelope (below). Validation errors `422` |
| Long-running work 💡 | `POST` returns **`202 Accepted`** + `{ "id": "…", "status": "QUEUED" }` and `Location` header; client **polls** `GET …/{id}`. (SSE/WebSocket can be added later; polling matches the AI brief: "Request job status → Read persisted results".) |
| Authorization 💡 | every team-scoped route checks the caller's `team_members.role` from the DB (see `03` §4) |
| Idempotency 💡 | state-changing `POST`s that create jobs accept optional `Idempotency-Key` header |
| CSRF 💡 | state-changing requests with an unexpected `Origin` are rejected |

### Error envelope 💡 (mirrors `contracts/ai_contracts.py → ErrorInfo`)

```json
{
  "error": {
    "code": "REPOSITORY_NOT_FOUND",
    "message": "The repository is not accessible to the CloudPilot GitHub App.",
    "correlation_id": "6f0f0b1e-3d41-4f6c-a0a7-2c4f1a2f9a10",
    "details": {}
  }
}
```

| HTTP | Typical `code` |
|---|---|
| 400 | `VALIDATION_ERROR` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN`, `PLAN_LIMIT_REACHED` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT` (e.g. deployment already running) |
| 422 | `VALIDATION_ERROR` (FastAPI/Pydantic) |
| 429 | `RATE_LIMITED` |
| 502/504 | `UPSTREAM_ERROR`, `STAGE_TIMEOUT` |

## 2. Implemented ✅

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health/db` | – | DB connectivity |
| GET | `/auth/github/login` | – | start GitHub sign-in (**navigate**, don't `fetch`) |
| GET | `/auth/github/callback` | – | GitHub returns here → sets cookie → redirect to `{FRONTEND_URL}/dashboard` (failure → `/login?error=github_failed`) |
| GET | `/auth/me` | ✔ | current user (`id, github_user_id, name, email, avatar_url`) |
| POST | `/auth/logout` | – | clear cookie (204) |
| POST | `/auth/dev-login` | – | **dev only**; body `{"github_user_id":"1001"}` → `{access_token, token_type}` |

## 3. Planned endpoints 💡

Role column: **M** = MEMBER+, **A** = ADMIN+, **O** = OWNER.

### 3.1 Teams & billing
| Method | Path | Role | Notes |
|---|---|:-:|---|
| GET | `/teams` | M | teams of the caller (personal team created on first login) |
| GET | `/teams/{team_id}` | M | |
| PATCH | `/teams/{team_id}` | A | rename |
| GET | `/teams/{team_id}/members` | M | |
| POST | `/teams/{team_id}/members` | A | add by GitHub username/email (invite flow TBD) |
| PATCH | `/teams/{team_id}/members/{user_id}` | O | change role; cannot remove last OWNER |
| DELETE | `/teams/{team_id}/members/{user_id}` | A | |
| GET | `/teams/{team_id}/subscription` | M | current plan + usage vs `limits` |
| GET | `/plans` | – | catalog |

### 3.2 Projects
| Method | Path | Role | Notes |
|---|---|:-:|---|
| GET | `/teams/{team_id}/projects` | M | `?status=ACTIVE` |
| POST | `/teams/{team_id}/projects` | A | enforces `max_projects` |
| GET | `/projects/{project_id}` | M | |
| PATCH | `/projects/{project_id}` | A | name/description |
| POST | `/projects/{project_id}/archive` | A | **archive, never delete** |

### 3.3 Repositories, branches, commits
| Method | Path | Role | Notes |
|---|---|:-:|---|
| GET | `/github/installations` | A | GitHub App installations visible to the user |
| GET | `/github/installations/{id}/repositories` | A | pick a repo |
| POST | `/projects/{project_id}/repositories` | A | `{github_repository_id}` → stores metadata only |
| GET | `/projects/{project_id}/repositories` | M | |
| GET | `/repositories/{repo_id}/branches` | M | |
| PUT | `/repositories/{repo_id}/deployment-branch` | A | `{branch_name}` — exactly one per repo |
| GET | `/repositories/{repo_id}/commits` | M | deployment-branch commits, paginated |
| POST | `/webhooks/github` | signature | GitHub App webhook (HMAC verified, **not** cookie-authed) → records commits, optionally triggers analysis |

### 3.4 Analysis (the AI brief's "Submit repo → Job ID → status → results")
| Method | Path | Role | Notes |
|---|---|:-:|---|
| POST | `/repositories/{repo_id}/analyses` | M | body `{ "commit_sha": null }` (default: head of deployment branch) → **202** `{id,status:"QUEUED"}` |
| GET | `/analyses/{analysis_id}` | M | status, timestamps, error, and `report` when finished |
| GET | `/repositories/{repo_id}/analyses` | M | history |
| GET | `/analyses/{analysis_id}/services` | M | normalized `services` rows |
| POST | `/analyses/{analysis_id}/answers` | M | user supplies `missing_info` answers → creates a new analysis |
| POST | `/analyses/{analysis_id}/cancel` | M | |

The report returned by the API and persisted in `analysis_data` contains evidence metadata only; repository source excerpts are never included.

Example — `GET /analyses/{id}` when blocked:
```json
{
  "id": "…", "repository_id": "…", "commit_sha": "c3d4e5f6…",
  "status": "BLOCKED",
  "started_at": "2026-11-02T10:00:03Z", "completed_at": "2026-11-02T10:00:41Z",
  "error": null,
  "report": {
    "schema_version": "1.0",
    "summary": "FastAPI service with PostgreSQL, Dockerfile present.",
    "services": [ { "name": "api", "service_type": "api", "language": "python", "framework": "fastapi", "port": 8000, "confidence": 0.93 } ],
    "blockers": [],
    "warnings": [ { "code": "NO_HEALTH_ENDPOINT", "severity": "WARNING", "message": "No health check route found.", "suggested_action": "Add GET /health." } ],
    "missing_info": [ { "key": "database_engine", "question": "Which managed database should be used?", "required": true } ],
    "overall_confidence": 0.88
  }
}
```

### 3.5 Architectures
| Method | Path | Role | Notes |
|---|---|:-:|---|
| POST | `/projects/{project_id}/architectures` | M | `{ "analysis_id": "…", "name": "Production" }` → **202** (runs Architecture Agent; only allowed on a validated, non-blocked analysis) |
| GET | `/projects/{project_id}/architectures` | M | |
| GET | `/architectures/{id}` | M | |
| GET | `/architectures/{id}/versions` | M | |
| GET | `/architecture-versions/{version_id}` | M | `architecture_data` (ArchitecturePlan) |
| POST | `/architectures/{id}/versions` | M | user edit → **new immutable version** |
| POST | `/architecture-versions/{version_id}/validate` | M | rule-based validation (security, completeness) |
| POST | `/architecture-versions/{version_id}/approve` | A | marks `APPROVED` (human decision) |
| GET | `/architecture-versions/{version_id}/cost-estimate` | M | latest `cost_estimates` row |
| POST | `/architecture-versions/{version_id}/cost-estimate` | M | recompute |

### 3.6 AWS accounts
| Method | Path | Role | Notes |
|---|---|:-:|---|
| POST | `/teams/{team_id}/aws-accounts` | A | creates a `PENDING_VERIFICATION` record + **External ID**; returns role-creation snippet (CloudFormation/Terraform) |
| POST | `/aws-accounts/{id}/verify` | A | STS `AssumeRole` test → `ACTIVE` / `VERIFICATION_FAILED` |
| GET | `/teams/{team_id}/aws-accounts` | M | |
| DELETE | `/aws-accounts/{id}` | A | disconnect (status `DISCONNECTED`, row kept) |

### 3.7 Deployments (Phase 2)
| Method | Path | Role | Notes |
|---|---|:-:|---|
| POST | `/projects/{project_id}/deployments` | A | `{architecture_version_id, aws_account_id, commit_sha}` → creates `QUEUED`; **409** if one is active; enforces monthly limit |
| GET | `/projects/{project_id}/deployments` | M | history |
| GET | `/deployments/{id}` | M | status, error |
| GET | `/deployments/{id}/steps` | M | ordered steps; failing step highlighted |
| GET | `/deployments/{id}/resources` | M | `infrastructure_resources` |
| POST | `/deployments/{id}/approve` | A | **human gate** before `terraform apply` |
| POST | `/deployments/{id}/cancel` | A | |
| POST | `/deployments/{id}/retry` | A | new deployment with `trigger_type=RETRY` |

### 3.8 Monitoring, incidents, healing (Phase 3)
| Method | Path | Role | Notes |
|---|---|:-:|---|
| PUT | `/deployments/{id}/monitoring` | A | `monitoring_configs` |
| GET | `/projects/{id}/alerts` | M | |
| GET | `/projects/{id}/incidents` | M | |
| GET | `/incidents/{id}` | M | with diagnosis and actions |
| POST | `/incidents/{id}/diagnose` | M | runs diagnosis agent (202) |
| GET | `/incidents/{id}/healing-actions` | M | |
| POST | `/healing-actions/{id}/approve` · `/reject` | A | `approvals` row; HIGH-risk actions always need it |

### 3.9 Costs & audit
| Method | Path | Role | Notes |
|---|---|:-:|---|
| GET | `/projects/{id}/costs?from&to` | M | `cost_records` vs `cost_estimates` |
| GET | `/teams/{id}/audit-logs` | A | 💡 |

## 4. Frontend integration notes ✅ (from the README)

```ts
const API = process.env.NEXT_PUBLIC_API_URL; // http://localhost:8000
export const login = () => { window.location.href = `${API}/auth/github/login`; };   // full navigation
export async function getMe() {
  const res = await fetch(`${API}/auth/me`, { credentials: "include" });
  return res.status === 401 ? null : res.json();
}
```
- Use `localhost` consistently (never mix with `127.0.0.1` — cookies are host-bound).
- `FRONTEND_URL` must equal the frontend origin exactly (no trailing slash) or CORS fails.
- Server components must forward the `access_token` cookie manually.
- Poll long jobs every 1–2 s with back-off; stop on terminal states `SUCCESS | BLOCKED | FAILED | TIMED_OUT | CANCELLED`.
- 📋 Provide an OpenAPI-generated TypeScript client so frontend types come from the backend schemas.