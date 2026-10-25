from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from AI.agents.aws_detection.prompts import (
    AWS_DETECTION_SYSTEM_PROMPT,
    build_aws_detection_prompt,
)
from AI.application.analysis.redactor import format_with_line_numbers
from AI.application.aws_detection.config_scanner import AwsConfigScan, AwsConfigScanner
from AI.application.ports.llm_provider import LLMProvider, LLMRequest
from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import AnalysisManifest
from AI.domain.aws_detection.models import (
    AwsConfigKind,
    AwsConfigStatus,
    AwsRequirement,
    AwsRequirementsResult,
)
from AI.domain.shared.errors import InvalidModelOutputError, RepositoryAccessError

MAX_STRING_CHARS = 300
MAX_CLARIFICATIONS = 10
SEED_CONFIDENCE = 0.7

# ---------------------------------------------------------------------------
# Pydantic schemas: used ONLY at the LLM boundary (same pattern as ManifestOut)
# ---------------------------------------------------------------------------


class AwsRequirementOut(BaseModel):
    service: str
    reason: str = ""
    evidence_files: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AwsDetectionOut(BaseModel):
    requirements: list[AwsRequirementOut] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    clarifications: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------

_SERVICE_ALIASES: dict[str, str] = {
    "s3": "S3",
    "lambda": "Lambda",
    "dynamodb": "DynamoDB",
    "sqs": "SQS",
    "sns": "SNS",
    "ses": "SES",
    "rds": "RDS",
    "aurora": "RDS",
    "elasticache": "ElastiCache",
    "ecr": "ECR",
    "ecs": "ECS",
    "eks": "EKS",
    "ec2": "EC2",
    "cloudfront": "CloudFront",
    "cloudwatch": "CloudWatch",
    "cloudwatchlogs": "CloudWatch",
    "secretsmanager": "Secrets Manager",
    "ssm": "SSM Parameter Store",
    "parameterstore": "SSM Parameter Store",
    "kinesis": "Kinesis",
    "stepfunctions": "Step Functions",
    "sfn": "Step Functions",
    "bedrock": "Bedrock",
    "cognito": "Cognito",
    "apigateway": "API Gateway",
    "eventbridge": "EventBridge",
    "iam": "IAM",
    "kms": "KMS",
    "route53": "Route 53",
    "opensearch": "OpenSearch",
    "redshift": "Redshift",
}


def normalize_service(raw: str) -> str:
    """Map free text such as 'Amazon S3' or 'aws_sqs' to one canonical service name."""
    cleaned = re.sub(r"^(amazon|aws)[\s_-]+", "", raw.strip(), flags=re.IGNORECASE).strip()
    key = re.sub(r"[^a-z0-9]", "", cleaned.lower())
    return _SERVICE_ALIASES.get(key, cleaned)


def _clip(text: str) -> str:
    return " ".join(text.split())[:MAX_STRING_CHARS]


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        clipped = _clip(item)
        if clipped:
            seen.setdefault(clipped, None)
    return list(seen)


@dataclass
class _Draft:
    reason: str
    files: list[str] = field(default_factory=list)
    confidence: float = 0.0


def _add_draft(
    drafts: dict[str, _Draft],
    service: str,
    reason: str,
    files: list[str],
    confidence: float,
) -> None:
    draft = drafts.setdefault(service, _Draft(reason=reason))
    if confidence > draft.confidence:
        draft.confidence = confidence
        draft.reason = reason or draft.reason
    for f in files:
        if f not in draft.files:
            draft.files.append(f)


@dataclass(frozen=True)
class _Seed:
    service: str
    reason: str
    evidence_file: str


def _seeds_from_manifest(manifest: AnalysisManifest, repo_files: frozenset[str]) -> tuple[_Seed, ...]:
    """Services the Analysis agent already found that are explicitly AWS-native (s3, sqs, ...)."""
    seeds: list[_Seed] = []
    for comp in manifest.components:
        for dep in comp.dependencies:
            key = re.sub(r"[^a-z0-9]", "", dep.name.lower())
            service = _SERVICE_ALIASES.get(key)
            evidence = (dep.evidence_file or "").lstrip("/")
            if service and evidence in repo_files:
                seeds.append(
                    _Seed(
                        service=service,
                        reason=f"Declared service dependency '{dep.name}' in component '{comp.name}'.",
                        evidence_file=evidence,
                    )
                )
    return tuple(seeds)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AwsDetectionAgent:
    """Implements the AwsRequirementsDetector port.

    Flow: deterministic scan signals + manifest seeds -> redacted excerpts ->
    one LLM call -> code verification (evidence must exist) -> immutable domain result.
    The LLM is skipped entirely when there is nothing for it to read.
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        reader: RepositoryReader,
        scanner: AwsConfigScanner,
        access_token: str = "",
        max_files: int = 6,
        max_chars_per_file: int = 6_000,
        max_parse_retries: int = 2,
    ) -> None:
        self._llm = llm
        self._reader = reader
        self._scanner = scanner
        self._access_token = access_token
        self._max_files = max_files
        self._max_chars_per_file = max_chars_per_file
        self._max_parse_retries = max_parse_retries

    async def detect(
        self, report: AnalysisManifest, config: AwsConfigStatus
    ) -> AwsRequirementsResult:
        repo = report.repo
        repo_files = frozenset(await self._reader.list_files(repo, self._access_token))
        scan = await self._scanner.scan(repo)

        drafts: dict[str, _Draft] = {}
        unresolved: list[str] = []
        clarifications: list[str] = []

        seeds = _seeds_from_manifest(report, repo_files)
        for seed in seeds:
            _add_draft(drafts, seed.service, seed.reason, [seed.evidence_file], SEED_CONFIDENCE)

        paths = self._select_files(report, scan, repo_files)
        if paths:
            observations = await self._collect_observations(report, paths)
            out = await self._ask_llm(report, config, observations, seeds)
            for item in out.requirements:
                service = normalize_service(item.service)
                if not service:
                    continue
                valid_files = [
                    f for f in (p.strip().lstrip("/") for p in item.evidence_files) if f in repo_files
                ]
                if not valid_files:
                    unresolved.append(f"{service}: cited evidence files do not exist in the repository.")
                    continue
                _add_draft(drafts, service, _clip(item.reason), valid_files, item.confidence)
            unresolved.extend(out.unresolved)
            clarifications.extend(out.clarifications)

        requirements: list[AwsRequirement] = []
        for service in sorted(drafts):
            draft = drafts[service]
            try:
                requirements.append(
                    AwsRequirement(
                        service=service,
                        reason=draft.reason or "Detected from repository files.",
                        evidence_files=tuple(draft.files),
                        confidence=round(min(max(draft.confidence, 0.0), 1.0), 2),
                    )
                )
            except ValueError as exc:
                unresolved.append(f"{service}: {exc}")

        return AwsRequirementsResult(
            repo=repo,
            requirements=tuple(requirements),
            config=config,
            unresolved=tuple(_dedupe(unresolved)),
            clarifications=tuple(_dedupe(clarifications)[:MAX_CLARIFICATIONS]),
        )

    # -- internals ---------------------------------------------------------

    def _select_files(
        self,
        manifest: AnalysisManifest,
        scan: AwsConfigScan,
        repo_files: frozenset[str],
    ) -> tuple[str, ...]:
        ordered: list[str] = []
        for kind in (
            AwsConfigKind.IAC_TEMPLATE,
            AwsConfigKind.SDK_CLIENT,
            AwsConfigKind.REGION_SETTING,
            AwsConfigKind.CREDENTIALS_REFERENCE,
        ):
            ordered.extend(scan.files_for(kind))
        for comp in manifest.components:
            ordered.extend(ev.file.lstrip("/") for ev in comp.evidence)
        unique = dict.fromkeys(f for f in ordered if f in repo_files)
        return tuple(unique)[: self._max_files]

    async def _collect_observations(
        self, manifest: AnalysisManifest, paths: tuple[str, ...]
    ) -> list[str]:
        observations: list[str] = []
        for path in paths:
            try:
                raw = await self._reader.read_file(manifest.repo, path, self._access_token)
            except RepositoryAccessError:
                continue
            numbered = format_with_line_numbers(raw, path=path, max_chars=self._max_chars_per_file)
            observations.append(f"=== File: {path} ===\n{numbered}")
        return observations

    async def _ask_llm(
        self,
        manifest: AnalysisManifest,
        config: AwsConfigStatus,
        observations: list[str],
        seeds: tuple[_Seed, ...],
    ) -> AwsDetectionOut:
        config_kinds = tuple(k.value for k in AwsConfigKind if config.has(k))
        seed_hints = tuple(f"{s.service} (see {s.evidence_file})" for s in seeds)
        schema_json = json.dumps(AwsDetectionOut.model_json_schema(), indent=2)
        base_prompt = (
            build_aws_detection_prompt(
                manifest,
                config_kinds=config_kinds,
                observations=observations,
                seed_hints=seed_hints,
            )
            + f"\n\n### Expected JSON Schema\n```json\n{schema_json}\n```"
        )

        last_error: str | None = None
        for _ in range(self._max_parse_retries + 1):
            prompt = (
                base_prompt
                if last_error is None
                else f"{base_prompt}\n\nPrevious JSON output was invalid ({last_error}). "
                "Fix the JSON to strictly match the schema."
            )
            response = await self._llm.complete(
                LLMRequest(
                    system=AWS_DETECTION_SYSTEM_PROMPT,
                    user=prompt,
                    expect_json=True,
                    temperature=0.0,
                )
            )
            if response.finish_reason == "length":
                last_error = "Model output was truncated (finish_reason=length)"
                continue
            try:
                return AwsDetectionOut.model_validate_json(response.text)
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)

        raise InvalidModelOutputError(
            "AWS detection agent failed to produce valid AwsDetectionOut after "
            f"{self._max_parse_retries + 1} attempts: {last_error}"
        )
