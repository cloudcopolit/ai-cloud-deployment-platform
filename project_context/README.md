# CloudPilot — Project Context

> Single source of planning truth for the CloudPilot backend, database and AI orchestration layer.
> Written for **humans and AI coding assistants**: read this index, [`AGENTS.md`](AGENTS.md) and `01-current-state.md` before changing any code.

## What CloudPilot is (one paragraph)

CloudPilot connects to a GitHub repository, analyzes the application, proposes an AWS architecture, lets the user review and edit it, and (later) deploys it into the **user's own AWS account** with Terraform. Every commit, architecture version and deployment attempt is recorded, so history stays traceable. It is a graduation project for small development teams and startups.

## Reading order

| # | File | Read it when you need… |
|---|---|---|
| – | [`AGENTS.md`](AGENTS.md) | **rules and workflow for AI coding assistants** (start here if you are one) |
| 00 | [`00-project-overview.md`](00-project-overview.md) | the vision, user journey, scope, glossary |
| 01 | [`01-current-state.md`](01-current-state.md) | **what actually exists today**, gaps, known issues, next steps |
| 02 | [`02-system-architecture.md`](02-system-architecture.md) | the big picture: components, boundaries, data flow, topology |
| 03 | [`03-backend-architecture.md`](03-backend-architecture.md) | backend layers, folder structure, module-by-module design, conventions |
| 04 | [`04-database-design.md`](04-database-design.md) | DB principles, domains, rules, migration plan, ERD gaps & proposals |
| 05 | [`05-api-specification.md`](05-api-specification.md) | implemented + planned REST endpoints |
| 06 | [`06-ai-orchestration.md`](06-ai-orchestration.md) | Orchestrator, Analysis Agent, Architecture Agent, Comm. Module, LangGraph |
| 07 | [`07-workflows-and-sequences.md`](07-workflows-and-sequences.md) | sequence & state diagrams for every major flow |
| 08 | [`08-security.md`](08-security.md) | auth, RBAC, AWS access model, untrusted-repo rules, threat list |
| 09 | [`09-devops-and-deployment.md`](09-devops-and-deployment.md) | local env, Docker, CI, environments, how CloudPilot itself ships |
| 10 | [`10-testing-strategy.md`](10-testing-strategy.md) | test pyramid, what exists, what to add per module |
| 11 | [`11-implementation-roadmap.md`](11-implementation-roadmap.md) | ordered, dependency-aware plan from today to the final product |
| 12 | [`12-decisions-adr.md`](12-decisions-adr.md) | architectural decisions: accepted vs proposed |
| 13 | [`13-open-questions-and-risks.md`](13-open-questions-and-risks.md) | what the team must still decide; risk register |

Supporting material:

| Path | Contents |
|---|---|
| [`database/erd.md`](database/erd.md) | Mermaid ERD: overview + one diagram per domain (generated from the `.drawio`) |
| [`database/data-dictionary.md`](database/data-dictionary.md) | Every table & column, types, nullability, constraints (27 tables) |
| [`database/schema-full.sql`](database/schema-full.sql) | Draft PostgreSQL DDL for the whole target schema |
| [`diagrams/CloudPilot_ERD.drawio`](diagrams/CloudPilot_ERD.drawio) | Original editable ERD (open in draw.io) |
| [`contracts/ai-contracts.md`](contracts/ai-contracts.md) | AnalysisReport / ArchitecturePlan / error formats explained |
| [`contracts/ai_contracts.py`](contracts/ai_contracts.py) | The same contracts as Pydantic v2 code (draft) |

## Status legend (used everywhere)

| Mark | Meaning |
|---|---|
| ✅ **Implemented** | exists in the backend code today and is covered by tests where noted |
| 📋 **Planned** | stated in the backend README, the ERD or the AI brief, but not built |
| 💡 **Proposed** | a recommendation made while writing this folder; **not yet agreed by the team** |

Anything marked 💡 is a suggestion to review, not a decision. Decisions live in [`12-decisions-adr.md`](12-decisions-adr.md).

## Where this information came from

Three inputs were read in full:

1. **`backend.zip`** — the FastAPI backend (snapshot; latest file timestamps 2026‑10‑15). 107 files (85 with content, 22 empty). The empty ones include 16 stub files for the four feature modules `analysis`, `deployments`, `projects`, `repositories`, and an empty `.gitignore`.
2. **`CloudPilot_ERD.drawio`** — 24 tables, 43 relationships, 8 color-coded domains.
3. **`CloudPilot AI Team — Analysis & Orchestration Implementation Brief`** (PDF, 4 pages).

**Not seen** (so not documented as fact): the AI-layer code, the frontend, the root-level `README`, `ruff.toml`, and the CI workflows. The backend README refers to all of them (`../ruff.toml`, "the AI layer", "root README → Continuous integration"), so they exist somewhere in the monorepo. Where this folder makes assumptions about them it says so.

## Source-of-truth hierarchy (when documents disagree)

1. **The code and the Alembic migrations** — what is really deployed.
2. **The backend README** — team intent and conventions.
3. **The ERD** — target data model (already differs from the code in places; see `01-current-state.md` §5).
4. **The AI brief** — target AI workflow.
5. **This folder** — a synthesis. If it conflicts with 1–4, this folder is wrong; fix it.

## Keeping this folder alive

Update the matching file **in the same pull request** as the change:

| You changed… | Update |
|---|---|
| a model / migration | `04-database-design.md`, `database/*` (regenerate from models), `01-current-state.md` |
| an endpoint | `05-api-specification.md` |
| an agent contract | `contracts/*`, `06-ai-orchestration.md` |
| an architectural choice | add an ADR in `12-decisions-adr.md` |
| finished a roadmap item | tick it in `11-implementation-roadmap.md`, update `01-current-state.md` |

## Folder layout

```
.project-context/
├── README.md
├── AGENTS.md                      # rules + workflow for AI assistants
├── 00-project-overview.md
├── 01-current-state.md
├── 02-system-architecture.md
├── 03-backend-architecture.md
├── 04-database-design.md
├── 05-api-specification.md
├── 06-ai-orchestration.md
├── 07-workflows-and-sequences.md
├── 08-security.md
├── 09-devops-and-deployment.md
├── 10-testing-strategy.md
├── 11-implementation-roadmap.md
├── 12-decisions-adr.md
├── 13-open-questions-and-risks.md
├── database/    erd.md · data-dictionary.md · schema-full.sql
├── diagrams/    CloudPilot_ERD.drawio
└── contracts/   ai-contracts.md · ai_contracts.py
```

## What was verified (and what was not)

| Artifact | Verification |
|---|---|
| `database/schema-full.sql` | **Executed on PostgreSQL 16.15**: all 27 tables created; one-deployment-branch index, role `CHECK`, approvals exactly-one-subject `CHECK` and `RESTRICT` deletes were each tested to reject bad data |
| `contracts/ai_contracts.py` | **Run** under pydantic 2.14.1 (`python ai_contracts.py`); the example JSON in `contracts/ai-contracts.md` validates |
| `database/erd.md`, `data-dictionary.md`, `schema-full.sql` | generated from one spec, so they cannot disagree with each other; ERD columns cross-checked against the `.drawio` (24 tables) |
| Mermaid diagrams | written to avoid known syntax pitfalls; **not rendered** by a Mermaid engine here: preview once in GitHub/VS Code |
| Columns of `plans`/`subscriptions` | **inferred** (README/seed), verify against the models |
| CI workflows, frontend, AI code | **not seen** |
