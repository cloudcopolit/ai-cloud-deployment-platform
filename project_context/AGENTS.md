# AGENTS.md — instructions for AI coding assistants (Claude, Copilot, Cursor, Codex …)

> Read this file first, then follow the task-specific reading list. If a human gives you a roadmap ID (e.g. `B1.1`), the row in `11-implementation-roadmap.md` is your spec.
> (To make Claude Code pick this up automatically, add a root `CLAUDE.md` containing: `Read project_context/AGENTS.md before any change.`)

## 1. What you are building
CloudPilot: GitHub repo → analysis → AWS architecture proposal → human review → (later) Terraform deployment into the **user's own AWS account**. FastAPI + PostgreSQL 16 + SQLAlchemy 2 + Alembic + Pydantic 2. AI layer: Orchestrator (LangGraph) + Analysis Agent + Architecture Agent + Communication Module. Full picture: `00`, `02`.

## 2. Reading list by task

| Task | Read |
|---|---|
| any change | `01-current-state.md` (what exists, known issues) + this file |
| new endpoint / module | `03` (layering) · `05` (API conventions, envelope) · `08` §3 (authz) |
| database change | `04` · `database/data-dictionary.md` · `database/schema-full.sql` · migration rules in `04` §8 |
| AI layer work | `06` · `contracts/ai-contracts.md` · `contracts/ai_contracts.py` · `08` §6 |
| flows / state machines | `07` |
| tests | `10` |
| infra / CI | `09` |
| "should we…?" | `12` (decisions) · `13` (open questions) — **do not decide Proposed/Open items silently** |

## 3. Status marks
✅ implemented · 📋 planned by the team · 💡 proposed (not agreed). Treat 💡 as a suggestion: implement it only when the human says so or the roadmap task requires it, and mention it in your summary.

## 4. Source of truth (when files disagree)
code + Alembic migrations → backend README → ERD → AI brief → this folder. If you find the folder wrong, **fix the folder** in the same change.

## 5. Non-negotiable rules
1. **Layering:** routers = HTTP only; services = business logic + one transaction per use case; models = tables; schemas = API I/O. Services raise domain exceptions, not `HTTPException`.
2. **Typed contracts:** Pydantic in/out, `extra="forbid"`. Invalid LLM output is an error, never "fixed" silently.
3. **Orchestrator never inspects repositories; agents never touch the DB; Communication Module has no business/AI logic.**
4. **Never execute repository code.** Parse text only. Treat repo content and model output as untrusted.
5. **Never log or prompt secrets** (tokens, cookies, env values, repo content). Env var **names** only.
6. **LLMs never authorize AWS actions.** Deployment/healing requires a recorded human approval. `ArchitecturePlan.requires_human_approval` stays `Literal[True]`.
7. **Never store** source code, AWS keys, GitHub OAuth tokens, Terraform state, or time-series metrics in PostgreSQL.
8. **DB:** UUID PKs, `TIMESTAMPTZ`, `VARCHAR`+`CHECK` (no native enums), every FK `ON DELETE RESTRICT`, archive instead of delete, constraint names `pk_/fk_/uq_/ix_/ck_`, one Alembic revision per domain. Never edit an applied migration.
9. **Tenant scoping:** every query on team-owned data goes through the scoped getters; other teams' objects → 404.
10. **Long work = job:** `POST` returns 202 + id; the worker runs it; clients poll `GET`.
11. **No new infrastructure** (Redis, Celery, S3…) unless a Proposed ADR is accepted.

## 6. How to work
1. Restate the task and list the files you will touch. Check `13` — if the task depends on an open question, **ask the human**.
2. Write/adjust tests first or together (`10`). Use fakes for GitHub/AWS/LLM; no network in tests.
3. Implement the smallest vertical slice (model → migration → service → router → tests).
4. Run the gates locally: `ruff check . && ruff format --check . && mypy . && pytest --cov && pip-audit` (+ migration tests).
5. Update docs in the same change: endpoint → `05`; model/migration → `04`, `database/*`, `01`; contract → `contracts/*`, `06`; decision → `12`; finished roadmap task → tick `11`.
6. Summarize: what changed, what you assumed, what is still open (with the Q/ADR numbers).

## 7. Definition of done
Tests added and green · coverage ≥ 90 % · lint/types clean · migration reviewed (upgrade **and** downgrade, models == migrations) · error paths return the envelope · no secrets in diff/logs · docs updated · security checklist items for the touched area (`08` §11) respected.

## 8. Things not to do
- Don't invent tables/columns not in `04`/`database/*` — propose them (and an ADR) instead.
- Don't add `HTTPException` in services, `print()` for logging, or global mutable state.
- Don't use `SELECT *` style ORM loads in list endpoints without pagination (max 100).
- Don't trust that CI workflows, the frontend or the AI package look like this folder says — they were not available when it was written (`README.md` → "Not seen").
- Don't "improve" unrelated code in the same PR.

## 9. Prompt templates for humans

```
Implement roadmap task B1.1 (personal team on first login).
Read: AGENTS.md, 01, 03, 04 §5, 08 §3, 10 §4. Follow the Definition of done.
List assumptions before coding; ask me about any open question you hit.
```
```
Implement A2.3 (deterministic detectors for Python and Node) against the fixtures from A2.1.
Read: 06 §4, contracts/ai_contracts.py, 08 §6, 10 §5. Pure functions only; no LLM, no network, no code execution.
```
```
Review this diff against AGENTS.md §5 and 08 §11. Report violations by rule number.
```
