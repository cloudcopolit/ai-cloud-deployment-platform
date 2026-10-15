# AI layer

This directory will hold CloudPilot's AI components: specialized agents, an
orchestrator that coordinates them, the tools agents may call, prompt
templates, and workflow definitions.

> **Current state:** no AI code is on the default branch yet. The directories
> below are placeholders. A *Code Architect* prototype is being developed on a
> feature branch and will be validated by the checks described here when it is
> merged. Nothing in this document should be read as an implemented feature.

## Intended layout

```text
ai/
├── agents/
│   ├── orchestrator/    # Planned: coordinates analysis → plan → validation → approval
│   ├── code_analyzer/   # Planned: identifies runtime, dependencies, ports, health checks
│   ├── architecture/    # Planned: proposes a cloud resource plan
│   ├── terraform/       # Planned: generates infrastructure-as-code
│   └── validator/       # Planned: checks generated plans and application behavior
├── prompts/             # Planned: prompt templates
├── tools/               # Planned: tools exposed to agents
├── workflows/           # Planned: workflow definitions
├── tests/               # Planned: cross-agent and contract tests
├── requirements-dev.txt # Shared lint/type-check tools CI installs for every project
└── mypy.ini             # Default type-checking policy for projects without their own
```

## How CI finds and checks AI code

The [AI workflow](../.github/workflows/ai.yml) discovers projects
automatically; nobody maintains a list of agents or files.

- **A project is any directory under `ai/` containing `pyproject.toml` or
  `requirements.txt`.** The whole of `ai/` can become one project, individual
  agents can be separate projects, or both (a nested project is checked on its
  own and excluded from its parent's run).
- For each project CI runs, from the project directory:
  1. install: `pip install -r requirements.txt` (plus `requirements-dev.txt` if
     present), or `pip install -e ".[dev]"` for a `pyproject.toml` project;
  2. `ruff check .` and `ruff format --check .` using the shared
     [`ruff.toml`](../ruff.toml);
  3. `mypy .` using the project's own mypy configuration, or
     [`ai/mypy.ini`](mypy.ini) if it has none;
  4. `pytest -m "not live_llm"`.
- Discovery **fails** if a `.py` file is outside every project, or if a project
  has no `test_*.py` / `*_test.py` files. Adding a new agent therefore means
  adding a manifest and tests, and CI picks it up with no workflow change.
- The required status check is the aggregate **`AI checks`** job. It passes
  with a notice while no AI projects exist.
- The Security workflow runs `pip-audit` on every discovered project's
  dependencies, and repository-wide checks validate the syntax of every JSON,
  YAML, and TOML file here (for example prompt or workflow definitions).

## Testing conventions

- **Declare test dependencies in the project** (pytest in `requirements.txt`,
  or a `dev` extra in `pyproject.toml`). CI adds only Ruff and mypy.
- **Tests must be deterministic and offline by default.** Use fakes, fixtures,
  or recorded responses for model calls; never require a paid API key.
  CI provides no AI provider credentials.
- Tests that genuinely need a live model must be marked
  `@pytest.mark.live_llm` (register the marker in the project's pytest
  configuration). They never run in CI and must be run deliberately.
- Treat model output as untrusted: test that agents validate structured output
  against schemas, bound retries, and never use model output as authorization.
- As agent interfaces and tool contracts are defined, add contract tests that
  pin their input/output schemas, and orchestration tests that drive agents
  through fakes.

## Running the checks locally

From a project directory (for example `ai/agents/orchestrator` once it exists):

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r ../../requirements-dev.txt   # adjust the relative path
ruff check . && ruff format --check .
mypy --config-file ../../mypy.ini .   # omit --config-file if the project has its own
pytest -m "not live_llm"
```

To preview what CI will discover: `python .github/scripts/discover_ai_projects.py`
from the repository root.
