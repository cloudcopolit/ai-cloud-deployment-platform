# 13 · Open Questions & Risk Register

> Open questions are decisions the **team** must make (not Claude). When one is decided, write an ADR (`12`) and delete it here.

## 1. Open questions

| # | Question | Why it matters | Recommendation 💡 | Owner | Needed by |
|---|---|---|---|---|---|
| **Q-1** | Where does the AI layer live (sibling package vs separate service) and where do shared contracts live? | import rules, CI, deploy | sibling `ai/` package, in-process, shared `contracts` package (ADR-009/018) | AI + Backend | before A1 |
| **Q-2** | Which LLM provider/model, and what may be sent to it (code excerpts)? Retention and privacy statement? | cost, quality, customer trust | one provider behind an adapter; send only redacted excerpts; document it in the UI | AI lead | before A2.6 |
| **Q-3** | Can the same GitHub repo be connected to several projects (code: yes, ERD: global unique)? | `repositories` uniqueness, webhooks routing | allow per project (current code) and route webhooks by `github_repository_id` → many repos | Backend | before B2.2 |
| **Q-4** | Team invitations: add by GitHub username only, or invite by email with accept flow? | `teams` module scope | MVP: add existing users by GitHub username; invites later | Backend/Product | before B1.3 |
| **Q-5** | Is AWS discovery of existing infrastructure part of the MVP (brief diagram shows it)? Where are findings stored? | extra IAM role, extra complexity | defer; if needed store in `analysis_data` (no new table) | AI + Product | before A3.4 |
| **Q-6** | Where does the Terraform runner execute (ECS one-off task, CodeBuild, local container for demo)? | isolation, cost, demo simplicity | local sandbox container for demo; ECS task/CodeBuild for pilot | Backend/DevOps | before D6 |
| **Q-7** | Which stacks are officially supported in the MVP? | defines `UNSUPPORTED_STACK`, fixtures, templates | Python (FastAPI/Django/Flask), Node (Express/Next.js), Dockerfile-based apps; others → BLOCKED with explanation | Team | before A2.3 |
| **Q-8** | Deployment patterns for MVP (ECS Fargate + ALB + RDS only, or also Lambda/static S3+CloudFront)? | size of Architecture Agent and Terraform templates | start with 2: static site, container + RDS | Team | before A4.1 |
| **Q-9** | Billing: real payments (Stripe) or plans only as limits? | scope | limits only for the graduation scope | Product | before B1.4 |
| **Q-10** | Monitoring stack for Phase 3: Prometheus, CloudWatch, or both? | what runs in the customer account | CloudWatch first (no extra infra in customer account) | Team | Phase 3 |
| **Q-11** | Does a push to the deployment branch trigger an analysis automatically? Auto-deploy ever? | cost, safety | analysis on push optional per project; **no auto-deploy** without explicit opt-in + approval | Product | B2.3 |
| **Q-12** | Region(s) and data residency for CloudPilot itself and for default customer deployments | latency, compliance | one region; customer region chosen per AWS account | Team | before D1 |
| **Q-13** | Frontend contract: generate a TypeScript client from OpenAPI, and expose JSON Schema of `AnalysisReport`? | frontend/backends drift | yes, generate in CI | Frontend + Backend | B3 |
| **Q-14** | Language of the product UI/docs (English/Arabic)? | i18n, LLM output language | English product, keep prompts and contracts English; consider Arabic UI later | Product | before frontend polish |

## 2. Risk register

Likelihood (L) and Impact (I): 1 low – 3 high. Score = L × I.

| # | Risk | L | I | Score | Mitigation | Owner |
|---|---|:-:|:-:|:-:|---|---|
| R1 | **Scope creep**: 27 tables + 3 agents + Terraform in one semester | 3 | 3 | **9** | enforce the cut line (`11` §7); MVP-1 → MVP-2 → MVP-3 gates; don't build Phase 3 before MVP-2 | lead |
| R2 | LLM output unstable / invalid JSON | 3 | 2 | 6 | deterministic-first (ADR-015), schema validation, 1 repair, recorded cassettes | AI |
| R3 | Analysis accuracy too low on real repos | 2 | 3 | 6 | golden + evaluation set early (A2.1), confidence + `missing_info` instead of guessing | AI |
| R4 | Security incident on customer AWS (confused deputy, over-broad role) | 1 | 3 | 3 | External ID, two roles, permissions boundary, security checklist (`08` §11) before any real account | Backend |
| R5 | Prompt injection / malicious repo | 2 | 3 | 6 | data-only prompts, no tools, never execute, fixtures | AI |
| R6 | GitHub App setup/permissions delays | 2 | 2 | 4 | start B2.1 early; fake GitHub for all tests so work isn't blocked | Backend |
| R7 | Terraform generation is a bottomless pit | 3 | 3 | **9** | templates per component type, 2 patterns only (Q-8), validate/tflint, plan-only fallback for demo | Backend/AI |
| R8 | LLM / AWS cost overruns during development | 2 | 2 | 4 | budgets/alarms, sandbox account, caching, `agent_runs.usage` | Lead |
| R9 | Contract drift between AI layer and backend | 2 | 2 | 4 | shared package + contract tests in both CIs (ADR-018) | Both |
| R10 | Background job reliability (stuck/duplicated jobs) | 2 | 2 | 4 | `SKIP LOCKED`, heartbeat, sweeper, idempotent persistence, tests | Backend |
| R11 | Data loss (no backup restore drill) | 1 | 3 | 3 | PITR/dump + one restore drill | DevOps |
| R12 | Cookie/CORS/domain problems at demo time | 2 | 2 | 4 | share parent domain, staging rehearsal, checklist from README | Backend/Frontend |
| R13 | Unseen parts (frontend, AI code, CI) differ from assumptions in this folder | 2 | 2 | 4 | verify `01` "Not seen" list; correct the docs (source-of-truth hierarchy) | Lead |
| R14 | Key-person dependency (one person knows Terraform/AWS) | 2 | 2 | 4 | pair on D5/D6, document runbooks | Lead |
| R15 | Legal/privacy: analyzing customers' private code, sending excerpts to an LLM | 2 | 3 | 6 | explicit consent text, minimal excerpts, provider with no-training terms (Q-2) | Lead |

## 3. Assumptions in this folder that must be verified

1. Columns of `plans`/`subscriptions` in `database/*` are inferred from the README/seed, not from the models.
2. CI workflows, root `README`, `ruff.toml`, frontend and AI-layer code were **not** available.
3. `ai_contracts.py` is a draft proposal; the AI team owns the final field set.
4. Timeouts, estimates and sizes are starting points.
