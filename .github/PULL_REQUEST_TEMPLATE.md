## Summary

<!-- What problem does this change solve, and how? -->

Related issue: <!-- Closes #... -->

## Target branch

<!-- Recommended flow: feature -> dev -> testing -> main (production). -->
- [ ] The pull request targets the intended branch.
- [ ] If targeting `main` (production), this change has already passed through `testing`.

## Changes

<!-- List the important changes and any trade-offs or follow-up work. -->

## Testing

<!-- What did you run, and what was the result? Paste commands or short output.
     If behavior changed without a test, explain why. -->

- [ ] I added or updated tests for the behavior I changed.
- [ ] I ran the checks for the components I touched (see CONTRIBUTING.md, "Reproduce CI locally").
- [ ] All CI checks pass, or I explained below why a failure is unrelated to this change.

## Impact

<!-- Tick everything that applies and describe it above. -->
- [ ] Database migration (describe whether it is reversible and safe for existing data)
- [ ] API contract change between backend and frontend
- [ ] AI/LLM behavior, prompts, or agent tools
- [ ] Infrastructure, IAM permissions, or deployment behavior
- [ ] New or changed environment variables (`.env.example` updated)
- [ ] Documentation updated
- [ ] None of the above

## Security

- [ ] No secrets, real credentials, account identifiers, Terraform state, or sensitive data are included.
- [ ] Changes to authentication, authorization, data handling, or CI permissions are described above.
- [ ] I have read the [Code of Conduct](../CODE_OF_CONDUCT.md).
