# Security Policy

## Project status

CloudPilot is under active development and is currently a scaffold. There are no released versions or runnable application services to designate as supported. Security reports about the repository and its planned workflows are still welcome.

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue or pull request. Use GitHub's **Report a vulnerability** feature on this repository if it is enabled. Otherwise, contact a repository maintainer privately through GitHub and ask for a secure reporting channel.

Include the affected file or component, the potential impact, and concise reproduction steps. Avoid sending credentials, personal data, or live AWS account details. Please allow maintainers time to investigate and coordinate a fix before making a report public.

## Security guidance for contributors and users

- Never commit API keys, cloud credentials, access tokens, private keys, or real environment files.
- Treat AI-generated infrastructure and commands as untrusted until reviewed. Inspect Terraform plans and IAM permissions before applying changes.
- Use a sandbox AWS account with least-privilege credentials for any future deployment testing.
- Do not include secrets or sensitive infrastructure details in logs, prompts, test fixtures, or issue reports.
- Revoke and rotate any credential that may have been exposed, and report the exposure privately.
