# Contributing to CloudPilot

Thanks for helping improve CloudPilot. This is a private project; this guide is for authorized team collaborators, not public contributions. The repository is currently a project scaffold: most application directories do not yet contain runnable services or local setup commands. Check the current implementation before relying on roadmap descriptions.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md) and [Security Policy](SECURITY.md).
- Search existing issues and pull requests to avoid duplicating work.
- For a significant change, open an issue first to agree on the scope and approach.
- Work only with credentials and AWS accounts you are authorized to use. Never commit credentials, customer data, or generated state files.

## Make a change

1. Create a focused branch from `dev` (for example, `docs/contributing-guide` or `feat/architecture-validation`).
2. Keep the change small and aligned with the existing project structure.
3. Run the relevant checks available for the files you changed. If no check exists yet, say so in your pull request rather than claiming tests passed.
4. Update directly affected documentation and examples.
5. Open a pull request to `dev` using the repository template. Explain the problem, the solution, and any trade-offs or follow-up work.

## Branch promotion

- `dev` is the integration branch. Feature and fix branches should target `dev`.
- Promote the validated `dev` branch to `testing` with a pull request for pre-production verification.
- Promote the verified `testing` branch to `main`, which is the production branch.
- CI runs on pull requests targeting and pushes to `dev`, `testing`, and `main`. A green CI run does not deploy the application.
- The `dev` and `testing` branches must be created in GitHub before their workflows and protection rules can run.
- Do not merge directly to `main` for routine changes. Repository administrators should enforce this with branch protection and required reviews/checks.

## Pull request expectations

- One coherent change per pull request; link related issues.
- Include screenshots or sample output for user-facing changes when useful.
- Call out changes to infrastructure permissions, deployment behavior, or data handling.
- Do not include secrets, real account identifiers, `.tfstate` files, or generated credentials.
- Be responsive to review feedback and keep the discussion respectful.

## Commit messages

Use short, descriptive messages in the imperative mood, such as `docs: clarify the planned deployment flow` or `feat: validate architecture input`.

## Project checks

GitHub Actions runs CI on pull requests targeting and pushes to `dev`, `testing`, and `main`. The workflow checks whitespace, lints and tests Python components, audits dependencies, checks the React app (lint, typecheck, tests, build), and formats and validates Terraform when those components are present. CodeRabbit is configured to review pull requests targeting these branches.

To activate the component checks, add:

- `backend/pyproject.toml` or `ai/pyproject.toml` with a `dev` optional dependency group containing Ruff, pytest, and the component's test dependencies, plus pytest tests under the respective directory.
- `frontend/package.json`, a committed `frontend/package-lock.json`, and `lint`, `typecheck`, `test:ci`, and `build` scripts.
- Terraform configuration under `infrastructure/terraform/`; CI runs formatting and validates each directory containing `.tf` files without cloud credentials.

Empty scaffold directories are skipped. Once source files exist, missing project metadata or tests cause CI to fail instead of silently passing. Do not run Terraform against a real account as a substitute for validation. Repository administrators should require CI checks and reviews in branch protection for all three long-lived branches, and reserve production deployment credentials for `main` only.
