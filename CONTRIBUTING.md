# Contributing to CloudPilot

Thanks for helping improve CloudPilot. This is a private project; this guide is for authorized team collaborators, not public contributions. The project is in early development: the backend authentication slice and the frontend dashboard shell work, while the AI agents and infrastructure are still placeholders. Check the current implementation (and the status table in the [README](README.md#project-status)) before relying on roadmap descriptions.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md) and [Security Policy](SECURITY.md).
- Search existing issues and pull requests to avoid duplicating work.
- For a significant change, open an issue first to agree on the scope and approach.
- Work only with credentials and AWS accounts you are authorized to use. Never commit credentials, customer data, or generated state files.

## Make a change

1. Create a focused branch from `dev` (for example, `docs/contributing-guide` or `feat/architecture-validation`).
2. Keep the change small and aligned with the existing project structure.
3. Add or update tests for behavior you change, and run the checks for the components you touched (see [Reproduce CI locally](#reproduce-ci-locally)).
4. Update directly affected documentation and examples.
5. Open a pull request to `dev` using the repository template. Explain the problem, the solution, how you tested it, and any trade-offs or follow-up work.

## Branch promotion

- `dev` is the integration branch. Feature and fix branches target `dev`.
- Promote the validated `dev` branch to `testing` with a pull request for pre-production verification.
- Promote the verified `testing` branch to `main`, which is the production branch.
- CI runs on pull requests targeting, and pushes to, `dev`, `testing`, and `main`. A green CI run does not deploy anything.
- Do not merge directly to `main` for routine changes.

## Pull request expectations

- One coherent change per pull request; link related issues.
- Every CI check must pass (see [Required checks](#required-checks)). If a check fails for a reason unrelated to your change, say so in the pull request instead of working around it.
- Include screenshots or sample output for user-facing changes when useful.
- Call out database migrations, changes to infrastructure permissions, deployment behavior, AI/LLM behavior, or data handling.
- Do not include secrets, real account identifiers, `.tfstate` files, or generated credentials.
- Be responsive to review feedback and keep the discussion respectful.

Do not weaken a check to make it pass: no `continue-on-error`, `|| true`, blanket lint ignores, lowered coverage thresholds, or skipped tests without a reviewed reason. A narrowly scoped exception (for example a `# noqa: <rule> - <reason>` on one line) needs a justification in the code and in the pull request.

## Commit messages

Use short, descriptive messages in the imperative mood, such as `docs: clarify the planned deployment flow` or `feat: validate architecture input`.

## Required checks

These job names are stable and are the ones to require in branch protection:

| Check | Workflow | Covers |
|---|---|---|
| `Backend lint and types` | Backend | Ruff lint and format, mypy |
| `Backend tests` | Backend | pytest with PostgreSQL, coverage ≥ 90%, Alembic migration checks |
| `Frontend checks` | Frontend | Frozen-lockfile install, ESLint, TypeScript, Vitest, production build |
| `AI checks` | AI | Aggregate result of discovery plus Ruff, mypy, and offline pytest for every AI project |
| `Infrastructure checks` | Infrastructure | Terraform fmt/validate/TFLint (when present), Hadolint, Compose validation (overlays merged with their base), Trivy misconfiguration scan |
| `Secret scan` | Security | Gitleaks on the commits being merged |
| `Dependency audit` | Security | pip-audit (backend and AI projects), pnpm audit |
| `Repository hygiene` | Repository | Whitespace, Ruff on CI scripts, JSON/YAML/TOML syntax, Markdown links, actionlint, zizmor |

Workflows have no path filters, so each of these reports a result on every pull request. Checks for components that have no code yet (Terraform, AI projects) pass with an explicit notice saying what was skipped, and start enforcing automatically once code is added.

> **Repository plan limitation:** this repository is private on GitHub's Free plan, where branch protection rules and rulesets are unavailable. Until the organization upgrades (GitHub Team) or the repository becomes public, these checks are visible on every pull request but cannot be *enforced*; reviewers must not merge a pull request with a failing check.

## Reproduce CI locally

Run commands from the directory shown. Tool versions are pinned in `backend/requirements-dev.txt`, `ai/requirements-dev.txt`, `.github/requirements-ci.txt`, and `frontend/package.json`.

### Backend (`backend/`)

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .        # `ruff format .` to fix
mypy
# Tests need PostgreSQL. With the database from db.yml running:
docker exec -it cloudpilot-db psql -U cloudpilot -c "CREATE DATABASE cloudpilot_test;"   # once
pytest --cov
```

Tests always use `TEST_DATABASE_URL` (default `postgresql+psycopg://cloudpilot:cloudpilot@localhost:5432/cloudpilot_test`) and refuse to run against a database whose name does not end in `_test`, so your `.env` cannot point them at real data.

New Alembic revisions are automatically fixed and formatted by Ruff (configured in `alembic.ini`); this needs the development requirements installed.

The same suite also runs in Docker with an isolated, throwaway database:
`docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.example run --rm --build backend-tests`
(see [docs/environments.md](docs/environments.md#testing)).

### Frontend (`frontend/`)

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck               # runs `next typegen`, then `tsc --noEmit`
pnpm test
pnpm build
```

The build does not need the backend or any secrets.

### AI projects (`ai/…`)

See [ai/README.md](ai/README.md#running-the-checks-locally). To see what CI will check, run `python .github/scripts/discover_ai_projects.py` from the repository root.

### Repository, security, and infrastructure (repository root)

```bash
pip install -r .github/requirements-ci.txt
ruff check .github/scripts && ruff format --check .github/scripts
python .github/scripts/validate_structured_files.py
python .github/scripts/check_markdown_links.py
zizmor .github/workflows                                  # set GH_TOKEN for online audits
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -color
docker run --rm -v "$PWD:/repo" -w /repo ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact .
pip-audit -r backend/requirements.txt
(cd frontend && pnpm audit --audit-level high)
docker run --rm -v "$PWD:/repo" -w /repo aquasec/trivy:0.75.0 config --severity HIGH,CRITICAL .
docker compose -f backend/db.yml config --quiet
for env in dev test prod; do docker compose -f docker-compose.yml -f docker-compose.$env.yml --env-file .env.example config --quiet; done
```

The workflows pin these images by digest; the tags above are the same versions.

## Handling security findings

- **Leaked secret:** rotate or revoke the credential first; deleting it in a later commit does not remove it from history. Then remove it from the branch (rewrite the unmerged branch, or, after rotation, add the finding's fingerprint to a `.gitleaksignore` file with a comment explaining that the credential is revoked).
- **Vulnerable dependency:** upgrade to a fixed version. If no fix exists and the vulnerable code is not reachable, add a reviewed exception next to the tool's configuration (for example `auditConfig.ignoreGhsas` in `frontend/pnpm-workspace.yaml`) with the reason and the condition for removing it.
- **Infrastructure misconfiguration (Trivy):** fix the configuration. Suppress a rule only with an inline `trivy:ignore:<ID>` comment that states why the risk is accepted.

## Security-sensitive CI rules

- Workflows use the `pull_request` event only; do not add `pull_request_target` or `workflow_run` triggers that run pull-request code with secrets or write permissions.
- Keep `permissions: contents: read` and add broader permissions only to the specific job that needs them.
- Pin new third-party actions to a full commit SHA with a version comment, and new tool images to a digest.
- Never add `terraform apply`, cloud credentials, or deployment steps to validation workflows.
