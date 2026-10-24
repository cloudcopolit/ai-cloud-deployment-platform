# 07 · Workflows & Sequences

> ✅ = matches code today · 📋 = from the AI brief / README · 💡 = proposed.

## 1. Sign-in with GitHub ✅

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant API as FastAPI
    participant GH as GitHub
    participant DB as PostgreSQL
    B->>API: GET /auth/github/login
    API-->>B: 307 → GitHub authorize (scope read:user user:email)<br/>Set-Cookie oauth_state (HttpOnly, 10 min)
    B->>GH: user approves
    GH-->>B: 302 → /auth/github/callback?code&state
    B->>API: GET /auth/github/callback (+cookie)
    API->>API: compare_digest(state, cookie)
    API->>GH: POST access_token (code)
    GH-->>API: OAuth token (used once, not stored)
    API->>GH: GET /user (+ /user/emails if hidden)
    API->>DB: upsert users (by github_user_id)
    API-->>B: 302 → {FRONTEND_URL}/dashboard<br/>Set-Cookie access_token (HttpOnly, SameSite=Lax, 30 min)
    Note over API,GH: handled GitHub exchange/profile failures → 302 {FRONTEND_URL}/login?error=github_failed
    B->>API: GET /auth/me (cookie)
    API->>DB: load user
    API-->>B: UserRead
```
📋 **Next:** in the same transaction as `upsert_github_user` on first login, create a personal `team`, an `OWNER` `team_members` row and a `FREE` `subscription`.

## 2. Connect a repository 📋💡

```mermaid
sequenceDiagram
    autonumber
    participant U as User (ADMIN+)
    participant API
    participant GH as GitHub (App)
    participant DB
    U->>API: GET /github/installations
    API->>GH: list installations/repositories (user-to-server token)
    U->>API: POST /projects/{id}/repositories {github_repository_id}
    API->>DB: INSERT repositories (metadata only)
    API->>GH: list branches
    API->>DB: INSERT branches (default branch flagged)
    U->>API: PUT /repositories/{id}/deployment-branch {main}
    API->>DB: set is_deployment_branch (unique partial index)
    API->>GH: register/confirm webhook
    GH-->>API: POST /webhooks/github (push) [HMAC verified]
    API->>DB: INSERT commits (idempotent on repository_id+sha)
```
Signing in does **not** grant repo access; access comes from the GitHub App installation (README).

## 3. Analysis workflow (AI brief sequence, adapted to the schema) 📋

The brief's diagram, restated with our tables:

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as FastAPI
    participant DB as PostgreSQL
    participant W as Worker 💡
    participant O as Orchestrator
    participant CM as Comm. Module
    participant RA as Analysis Agent
    participant AWS as AWS Discovery (optional)
    participant AR as Architecture Agent

    U->>API: POST /repositories/{id}/analyses
    API->>DB: INSERT repository_analyses (QUEUED) + agent_runs
    API-->>U: 202 {job_id}
    W->>DB: claim job (SKIP LOCKED) → RUNNING
    W->>O: run(job)
    O->>CM: analyze repo & infra
    par repository
        CM->>RA: AnalysisRequest (+ resolved GitHub token inside CM)
        RA->>RA: fetch tree, parse files as data (no execution)
        RA-->>CM: AgentResult(AnalysisReport)
    and infrastructure (optional, read-only)
        CM->>AWS: discover resources (STS AssumeRole, read-only)
        AWS-->>CM: infra findings | error
    end
    CM-->>O: repo findings + infra findings
    O->>O: validate & combine → AnalysisReport
    O->>O: evaluate blockers (is_deployable)
    alt required info missing / blockers / unsupported
        O->>DB: save report, status BLOCKED
    else analysis sufficient
        O->>CM: submit AnalysisReport
        CM->>AR: generate plan
        AR-->>CM: ArchitecturePlan
        CM-->>O: plan
        O->>O: validate plan
        O->>DB: save architecture_versions + cost_estimates, status SUCCESS
    end
    U->>API: GET /analyses/{id}
    API->>DB: read persisted status/results
    API-->>U: JSON
```

## 4. Architecture editing & approval 📋 (Phase 2)

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Architecture Agent creates version N
    DRAFT --> DRAFT: user edits → NEW version N+1 (old kept, SUPERSEDED)
    DRAFT --> VALIDATED: rule checks pass
    DRAFT --> INVALID: rule checks fail
    INVALID --> DRAFT: user fixes (new version)
    VALIDATED --> APPROVED: ADMIN approves (human)
    APPROVED --> SUPERSEDED: newer version approved
    SUPERSEDED --> [*]
```
Version statuses are 💡 proposals (`architecture_versions.status` is an unconstrained string in the ERD).

## 5. Connect an AWS account 📋💡

```mermaid
sequenceDiagram
    autonumber
    participant U as User (ADMIN+)
    participant API
    participant DB
    participant STS as AWS STS
    participant C as Customer account
    U->>API: POST /teams/{id}/aws-accounts {aws_account_id, region}
    API->>DB: INSERT aws_accounts (PENDING_VERIFICATION, external_id=random)
    API-->>U: role template (trust CloudPilot principal + ExternalId condition)
    U->>C: creates IAM role from template
    U->>API: POST /aws-accounts/{id}/verify {role_arn}
    API->>DB: authorize aws_accounts/{id} against the caller's team
    API->>API: validate allowed partition, expected CloudPilot IAM role, and account ID matches the authorized record
    API->>STS: AssumeRole(role_arn, ExternalId)
    alt success
        STS-->>API: short-lived credentials (memory only)
        API->>DB: status ACTIVE, last_verified_at
    else denied
        API->>DB: status VERIFICATION_FAILED
    end
```
No access keys are ever collected or stored.

## 6. Deployment (Phase 2) 📋💡

```mermaid
sequenceDiagram
    autonumber
    participant U as User (ADMIN+)
    participant API
    participant DB
    participant W as Worker
    participant TF as Terraform runner (sandbox)
    participant AWS as Customer AWS
    U->>API: POST /projects/{id}/deployments {architecture_version, aws_account, commit}
    API->>DB: guard: version APPROVED, account ACTIVE, no active deployment, monthly quota
    API->>DB: INSERT deployments (QUEUED) + planned deployment_steps
    API-->>U: 202
    W->>DB: claim → RUNNING
    W->>TF: generate Dockerfile + Terraform from plan
    W->>DB: step results (GENERATE_*, BUILD, PUSH_IMAGE …)
    W->>TF: terraform init / plan (AssumeRole)
    TF->>AWS: read-only plan
    W->>DB: step PLAN_REVIEW → deployment awaits approval
    U->>API: POST /deployments/{id}/approve  ← human gate
    API->>DB: INSERT approvals (APPROVED, approved_by)
    W->>TF: terraform apply
    TF->>AWS: create resources
    W->>DB: INSERT infrastructure_resources and step results
    W->>AWS: health check
    W->>DB: status SUCCESS | FAILED (failing step + error_code)
```

Proposed ordered `step_type` values 💡: `VALIDATE_PLAN` → `GENERATE_DOCKERFILE` → `BUILD_IMAGE` → `PUSH_IMAGE` → `GENERATE_TERRAFORM` → `TERRAFORM_INIT` → `TERRAFORM_PLAN` → `AWAIT_APPROVAL` → `TERRAFORM_APPLY` → `HEALTH_CHECK` → `FINALIZE`. Terraform **state lives in the customer's own S3 bucket** (ADR‑013), never in PostgreSQL.

## 7. Deployment status machine 📋

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    QUEUED --> CANCELLED
    RUNNING --> SUCCESS
    RUNNING --> FAILED
    RUNNING --> CANCELLED
    FAILED --> [*]: user may start a RETRY deployment
    SUCCESS --> [*]
    CANCELLED --> [*]
```
`trigger_type`: `MANUAL`, `AUTO` (push to deployment branch), `RETRY`, `HEALING`. Step status: `QUEUED, RUNNING, SUCCESS, FAILED, SKIPPED`.

## 8. Monitoring → incident → self-healing (Phase 3) 📋💡

```mermaid
sequenceDiagram
    autonumber
    participant M as Monitoring (Prometheus/CloudWatch)
    participant API
    participant DB
    participant AG as Diagnosis/Healing Agent
    participant U as Human (ADMIN+)
    participant TF as Executor
    M->>API: alert (metric, threshold, actual)
    API->>DB: INSERT alerts (FIRING)
    API->>DB: INSERT incidents (OPEN, alert_id, deployment_id)
    API->>AG: diagnose(incident)  [agent_runs]
    AG-->>API: root_cause, diagnosis, proposed healing_actions + risk_level
    API->>DB: UPDATE incidents (INVESTIGATING), INSERT healing_actions (PROPOSED)
    alt healing action changes AWS
        API->>DB: INSERT approvals (PENDING)
        U->>API: approve / reject
        API->>TF: execute action only after authorized approval
    else action does not change AWS and policy allows auto-heal
        API->>TF: execute action
    end
    TF->>DB: healing_actions EXECUTING → SUCCEEDED/FAILED
    API->>DB: incident MITIGATING → RESOLVED → CLOSED
```
"Policy-based self-healing" (README Phase 3) means an explicit, reviewable policy may auto-execute only actions that do not change AWS. **Default = require approval.** Every AWS-changing action requires a recorded, authorized human approval before execution through the deploy-role boundary; an LLM never holds the authority itself.

## 9. Job claiming & recovery 💡

```mermaid
flowchart TD
    A[Worker loop] --> B{claim QUEUED job<br/>FOR UPDATE SKIP LOCKED}
    B -- none --> A
    B -- job --> C[status=RUNNING + heartbeat]
    C --> D[run Orchestrator]
    D --> E{outcome}
    E -- SUCCESS/BLOCKED/FAILED --> F[persist + finish]
    E -- exception --> G[ErrorInfo INTERNAL_ERROR → FAILED]
    H[Sweeper every minute] --> I{RUNNING and heartbeat stale?}
    I -- retryable --> J[re-queue]
    I -- else --> K[TIMED_OUT]
```