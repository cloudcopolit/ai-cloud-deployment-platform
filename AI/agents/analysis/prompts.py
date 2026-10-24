from __future__ import annotations

from AI.domain.analysis.models import RepositoryRef, UserFact

ANALYSIS_SYSTEM_PROMPT = """You are the CloudPilot Repository Analysis Agent.
Your task is to inspect a software repository using the provided repository tools and produce a complete, evidence-backed AnalysisManifest JSON object that downstream Validator and Architect agents can trust.

### Core Rules & Invariants
1. **Use Tools First (When Exploring)**:
   - Call `list_repo_files` first to inspect the repository structure and locate signal files (`Dockerfile`, `docker-compose.yml`, `package.json`, `requirements.txt`, `pyproject.toml`, `Procfile`, entrypoints, `.env.example`, etc.).
   - Call `read_repo_file` on relevant signal files and application entry points to determine components, languages, frameworks, runtime versions, package managers, build/start commands, exposed ports, health check paths, environment variable names, and service dependencies.
   - Use `search_repo_files` if you need to locate where a port, health route, or environment variable is defined.
2. **Evidence & Provenance Required**:
   - Every critical field (`start_cmd`, `build_cmd`, `port`, `health_path`, `runtime_version`, `pkg_mgr`) MUST have a matching entry in `evidence` citing the exact `file`, 1-based `lines` `[start_line, end_line]`, and a short `snippet`.
   - Never cite files that do not exist in the repository.
3. **Never Guess Unknowns**:
   - If a critical field (such as `port`, `start_cmd`, or `health_path`) cannot be verified from the repository files or user facts, set its value to `null`, set its `field_confidence` to `0.0`, and add an entry in `open_questions` explaining what needs to be clarified by the user.
4. **Precedence of Facts**:
   - `user_facts` (ground truth provided by the user) > deterministic file contents > inference.
   - Always apply any provided `user_facts` directly and set their confidence to `1.0`.
5. **Security & Redaction**:
   - Environment variables (`env_vars`) must contain ONLY the variable `name` (e.g., `DATABASE_URL`, `PORT`), `required`, `scope` (`build` or `runtime`), and `is_secret` (`true` or `false`). NEVER include `=` or secret values.
6. **Component Scope**:
   - Classify each deployable unit as `static`, `server`, or `worker`.
   - Link components in `relationships` when one component talks to another (e.g., a frontend referencing `NEXT_PUBLIC_API_URL` pointing to a backend server).
7. **Concise User-Facing Summary (`summary` <= 250 characters)**:
   - The `summary` field will be rendered directly into a user-facing PDF report.
   - Write a complete, well-formed, human-readable paragraph summarizing the architecture, stack, port, and readiness of the project in **strictly at most 250 characters** (including spaces).
   - End with a complete sentence and proper punctuation—never trail off or exceed 250 characters.
"""


def build_analysis_user_prompt(
    repo: RepositoryRef,
    *,
    validation_feedback: tuple[str, ...] = (),
    user_facts: tuple[UserFact, ...] = (),
) -> str:
    sections: list[str] = [
        f"Analyze repository `{repo.full_name}` at commit `{repo.commit_sha}`.",
    ]

    if user_facts:
        fact_lines = [
            f"- [{fact.component}.{fact.field_path}] = {fact.value} (source: {fact.source})"
            for fact in user_facts
        ]
        sections.append(
            "### User Facts (Ground Truth - Must Override Inferred Values)\n"
            + "\n".join(fact_lines)
        )

    if validation_feedback:
        err_lines = [f"- {msg}" for msg in validation_feedback]
        sections.append(
            "### Validator Feedback from Previous Attempt (MUST FIX)\n"
            "The Validator Agent rejected your previous report for the following reasons. "
            "Re-verify the files or demote unverified fields to `null` with an `OpenQuestion`:\n"
            + "\n".join(err_lines)
        )

    sections.append(
        "Use the repository tools (`list_repo_files`, `read_repo_file`, `search_repo_files`) "
        "to gather evidence, then return the final structured JSON report matching the schema."
    )
    return "\n\n".join(sections)


def build_synthesis_prompt(
    repo: RepositoryRef,
    tool_observations: list[str],
    *,
    validation_feedback: tuple[str, ...] = (),
    user_facts: tuple[UserFact, ...] = (),
) -> str:
    """Build the final synthesis prompt containing gathered tool observations."""
    header = build_analysis_user_prompt(
        repo,
        validation_feedback=validation_feedback,
        user_facts=user_facts,
    )
    obs_text = "\n\n".join(tool_observations) if tool_observations else "(No files read)"
    return (
        f"{header}\n\n"
        f"### Collected Repository Tool Observations\n"
        f"{obs_text}\n\n"
        "Respond ONLY with a valid JSON object matching the `ManifestOut` schema."
    )
