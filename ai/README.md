# AI layer (`cloudpilot_ai`)

The AI layer is one Python package, `cloudpilot_ai`, in `ai/src/`. It is a
**stateless library** (ADR-009): the backend worker imports it and calls its
public API; the package never imports the backend and never touches the
database. It receives everything it needs through *ports* (interfaces) that
the backend implements, and reports progress through an `EventSink`.

| Module | Status | Purpose |
|---|---|---|
| `contracts` | REAL | Pydantic v2 contracts shared with the backend (ADR-018): `AnalysisRequest`, `AnalysisReport`, `ArchitecturePlan`, `AgentResult`, `ErrorInfo`. Strict: unknown fields rejected. |
| `prototype` | SIMULATED, to be deleted | The earlier canned analyzer/architect. Replaced by the real orchestrator and agents (WORKLOG slices S2–S4). |

`WORKLOG.md` at the repository root tracks what is REAL, SIMULATED or MOCKED-ONLY.

## Rules

- Never import `app.*` (the backend). The backend depends on this package, not the reverse.
- Never execute code from an analyzed repository; parse text only.
- Never put secrets, tokens or source excerpts into contracts, events or logs. Env var **names** only.
- LLMs never authorize infrastructure changes; `ArchitecturePlan.requires_human_approval` is `Literal[True]`.

## How CI checks it

`ai/` is a single CI project (it has `pyproject.toml`). The [AI workflow](../.github/workflows/ai.yml)
discovers it with `.github/scripts/discover_ai_projects.py`, then from `ai/` runs
`pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`, `mypy .` (config in
[`mypy.ini`](mypy.ini)) and `pytest -m "not live_llm"`.

Tests are deterministic and offline: GitHub, LLM providers and AWS are replaced by fakes.
Tests that need a live model are marked `@pytest.mark.live_llm` and never run in CI.

## Running the checks locally

```bash
cd ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" -r requirements-dev.txt
ruff check . && ruff format --check . && mypy . && pytest -m "not live_llm"
```

Or, without a local Python 3.12, in the backend test image (see `Makefile`, target `check-ai`).
