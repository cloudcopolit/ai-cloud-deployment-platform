# Security Policy

## Project status

CloudPilot is in early development. There are no released versions or production deployments to designate as supported. Security reports about the repository, the implemented authentication flow, the CI configuration, and the planned workflows are welcome.

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue or pull request. Use GitHub's **Report a vulnerability** feature on this repository if it is enabled. Otherwise, contact a repository maintainer privately through GitHub and ask for a secure reporting channel.

Include the affected file or component, the potential impact, and concise reproduction steps. Avoid sending credentials, personal data, or live AWS account details. Please allow maintainers time to investigate and coordinate a fix before making a report public.

## Security guidance for contributors and users

- Never commit API keys, cloud credentials, access tokens, private keys, or real environment files. Use the `.env.example` files as templates; the real `.env` files are ignored by Git.
- If a secret is ever committed or pushed, even to a feature branch or in a commit that is later reverted, treat it as compromised: **revoke or rotate it immediately**, then report it privately. Removing it in a later commit does not remove it from Git history.
- Treat AI-generated infrastructure, commands, and model output as untrusted until validated and reviewed. Inspect Terraform plans and IAM permissions before applying changes.
- Use a sandbox AWS account with least-privilege credentials for any future deployment testing.
- Do not include secrets or sensitive infrastructure details in logs, prompts, test fixtures, or issue reports. AI tests must use fakes, not real provider keys.

## Automated checks

Every pull request and push to `dev`, `testing`, and `main` runs (see [CONTRIBUTING.md](CONTRIBUTING.md#required-checks)):

| Check | Tool |
|---|---|
| Secrets in commits | Gitleaks (pull-request commits; full branch history on push and weekly) |
| Vulnerable Python dependencies | pip-audit for the backend and every AI project (also weekly) |
| Vulnerable frontend dependencies | `pnpm audit --audit-level high` (also weekly) |
| Python security lint | Ruff `S` (flake8-bandit) rules |
| Infrastructure and Dockerfile misconfiguration | Trivy (HIGH and CRITICAL), Hadolint |
| GitHub Actions security | zizmor, actionlint |

CI workflows use read-only tokens, receive no repository secrets, never use `pull_request_target`, and never deploy. Actions are pinned to commit SHAs and tool images to digests.

GitHub CodeQL code scanning and the dependency-review action require GitHub Advanced Security for private repositories and are therefore not configured; enable them if the repository becomes public or the organization obtains GitHub Code Security.

### Reviewed exceptions

Exceptions to automated findings must be narrowly scoped, recorded next to the tool configuration with a reason and a removal condition, and called out in the pull request. Current exceptions:

| Finding | Where | Reason | Remove when |
|---|---|---|---|
| GHSA-vfj7-8cjw-p6xm (`braces` ≤ 3.0.3, high, DoS) | `frontend/pnpm-workspace.yaml` | No patched release exists; reached only through build tooling (shadcn CLI, eslint-config-next) that expands developer-written glob patterns, not the application's runtime | A patched `braces` release is available and resolved |
