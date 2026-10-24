from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import RepositoryRef
from AI.domain.aws_detection.models import AwsConfigFinding, AwsConfigKind, AwsConfigStatus

MAX_CHARS_PER_FILE = 200_000

SCANNABLE_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".kt", ".cs", ".rb", ".php",
    ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".tf", ".sh", ".env",
}
SCANNABLE_NAMES = {"Dockerfile", ".env", "cdk.json", "serverless.yml"}


@dataclass(frozen=True)
class _Rule:
    kind: AwsConfigKind
    detail: str
    path_glob: str | None = None
    content: re.Pattern[str] | None = None

    def matches(self, filename: str, text: str) -> bool:
        if self.path_glob is not None and not fnmatch(filename, self.path_glob):
            return False
        if self.content is not None and not self.content.search(text):
            return False
        return self.path_glob is not None or self.content is not None


RULES: tuple[_Rule, ...] = (
    _Rule(AwsConfigKind.IAC_TEMPLATE, "AWS CDK project", path_glob="cdk.json"),
    _Rule(AwsConfigKind.IAC_TEMPLATE, "Serverless Framework config", path_glob="serverless.yml"),
    _Rule(AwsConfigKind.IAC_TEMPLATE, "Terraform AWS provider", path_glob="*.tf",
          content=re.compile(r'provider\s+"aws"')),
    _Rule(AwsConfigKind.IAC_TEMPLATE, "SAM or CloudFormation template",
          path_glob="*.y*ml", content=re.compile(r"AWSTemplateFormatVersion|Transform:\s*AWS::Serverless")),
    _Rule(AwsConfigKind.SDK_CLIENT, "boto3 import",
          content=re.compile(r"\bimport boto3\b|\bfrom boto3\b")),
    _Rule(AwsConfigKind.SDK_CLIENT, "AWS JavaScript/TypeScript SDK import",
          content=re.compile(r"@aws-sdk/|require\(['\"]aws-sdk['\"]\)")),
    _Rule(AwsConfigKind.CREDENTIALS_REFERENCE, "AWS credentials referenced via environment or profile",
          content=re.compile(r"AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_PROFILE")),
    _Rule(AwsConfigKind.REGION_SETTING, "AWS region configured",
          content=re.compile(r"AWS_REGION|AWS_DEFAULT_REGION|region_name\s*=")),
    _Rule(AwsConfigKind.HARDCODED_CREDENTIALS, "Possible hardcoded AWS access key ID",
          content=re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
)


def _is_scannable(path: str) -> bool:
    p = PurePosixPath(path)
    return p.name in SCANNABLE_NAMES or p.suffix in SCANNABLE_SUFFIXES


class AwsConfigScanner:
    def __init__(self, reader: RepositoryReader) -> None:
        self._reader = reader

    async def scan(self, repo: RepositoryRef, access_token: str) -> AwsConfigStatus:
        findings: list[AwsConfigFinding] = []
        for path in await self._reader.list_files(repo, access_token):
            if not _is_scannable(path):
                continue
            text = (await self._reader.read_file(repo, path, access_token))[:MAX_CHARS_PER_FILE]
            name = PurePosixPath(path).name
            for rule in RULES:
                if rule.matches(name, text):
                    findings.append(AwsConfigFinding(kind=rule.kind, file=path, detail=rule.detail))
        return AwsConfigStatus(findings=tuple(findings))