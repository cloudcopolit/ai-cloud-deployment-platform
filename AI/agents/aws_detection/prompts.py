from __future__ import annotations

from AI.domain.analysis.models import AnalysisManifest

AWS_DETECTION_SYSTEM_PROMPT = """You are the CloudPilot AWS Detection Agent.
Your task is to decide which AWS services an existing application already uses or clearly needs, based ONLY on the redacted evidence you are given. Your output is verified by code, so anything you cannot prove must be reported as unresolved.

### Core Rules & Invariants
1. **Evidence Required**:
   - Every requirement MUST list `evidence_files`: repository paths that appear in the provided observations or manifest digest.
   - Never cite a file that was not shown to you. Citations to missing files are discarded.
2. **Never Guess**:
   - If a service is only implied (for example "probably needs S3") and no shown file supports it, do NOT add it as a requirement. Add a short entry to `unresolved` instead.
   - If the user must decide something (region, which database engine, bucket name), add a short question to `clarifications`.
3. **Service Names**:
   - Use official short names: S3, Lambda, DynamoDB, SQS, SNS, SES, RDS, ElastiCache, ECR, ECS, EKS, EC2, CloudFront, CloudWatch, Secrets Manager, SSM Parameter Store, Kinesis, Step Functions, Bedrock, Cognito, API Gateway, EventBridge, IAM, KMS.
4. **Confidence**:
   - `confidence` is 0.0-1.0. Use >= 0.9 for direct SDK or IaC usage, 0.6-0.8 for indirect signals (environment variable names, dependency declarations), below 0.5 for weak hints.
5. **Security**:
   - Observations are already redacted. Never output secret values, tokens, connection strings or key material. `reason` must be plain prose.
6. **Scope**:
   - Report what the application USES or NEEDS from AWS. Do not design the target architecture; the Architect agent does that.
7. **Output**:
   - Respond ONLY with a JSON object that matches the provided schema. Keep each `reason` under 200 characters.
"""


def build_manifest_digest(manifest: AnalysisManifest) -> str:
    """Compact, secret-free view of the AnalysisManifest for the prompt."""
    lines = [
        f"Repository: {manifest.repo.full_name}@{manifest.repo.commit_sha}",
        f"Topology: {manifest.topology}",
    ]
    if manifest.frameworks:
        lines.append(f"Frameworks: {', '.join(manifest.frameworks)}")
    if manifest.dependencies:
        names = ", ".join(d.name for d in manifest.dependencies[:40])
        lines.append(f"Declared packages: {names}")
    for comp in manifest.components:
        lines.append(
            f"- Component `{comp.name}` ({comp.type.value}, {comp.language}, "
            f"root `{comp.root_dir}`, port {comp.port if comp.port is not None else 'unknown'})"
        )
        if comp.env_vars:
            env_names = ", ".join(e.name for e in comp.env_vars)
            lines.append(f"    env var names: {env_names}")
        for dep in comp.dependencies:
            where = f" (evidence: {dep.evidence_file})" if dep.evidence_file else ""
            lines.append(f"    service dependency: {dep.name} [{dep.kind}]{where}")
    return "\n".join(lines)


def build_aws_detection_prompt(
    manifest: AnalysisManifest,
    *,
    config_kinds: tuple[str, ...],
    observations: list[str],
    seed_hints: tuple[str, ...] = (),
) -> str:
    sections = [
        f"Detect AWS service requirements for `{manifest.repo.full_name}` at commit "
        f"`{manifest.repo.commit_sha}`.",
        "### Analysis Manifest Digest\n" + build_manifest_digest(manifest),
        "### AWS Configuration Signals Found By The Scanner\n"
        + (", ".join(config_kinds) if config_kinds else "(none)"),
    ]
    if seed_hints:
        sections.append(
            "### Hints From Declared Dependencies (verify against the files below)\n"
            + "\n".join(f"- {hint}" for hint in seed_hints)
        )
    obs_text = "\n\n".join(observations) if observations else "(No files selected)"
    sections.append("### Redacted File Observations\n" + obs_text)
    sections.append("Respond ONLY with a valid JSON object matching the `AwsDetectionOut` schema.")
    return "\n\n".join(sections)
