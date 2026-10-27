"""Committed-secret detection and redaction (08 §6, A2.7).

Findings carry the file path, line and secret KIND. The matched value never leaves this
module: it is not logged, stored, returned or put into a prompt. `redact` is the same
pattern set, used by the LLM gateway before any text reaches a provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cloudpilot_ai.analysis.facts import Facts, line_of
from cloudpilot_ai.analysis.files import Kind
from cloudpilot_ai.contracts import Severity

# kind -> pattern. High-signal formats only: a false "secret committed" blocks a deployment.
PATTERNS: dict[str, re.Pattern[str]] = {
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS secret access key": re.compile(
        r"(?i)aws_?secret_?access_?key[\"'\s:=]+[\"']?([A-Za-z0-9/+=]{40})\b"
    ),
    "private key": re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "GitHub token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{60,255})\b"
    ),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "Stripe live key": re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "OpenAI API key": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    "Anthropic API key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b"),
    "SendGrid API key": re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    "Twilio API key": re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
}
# assignments in committed .env files: KEY=value where the key looks sensitive
SENSITIVE_KEY = re.compile(
    r"(?i)(secret|password|passwd|pwd|token|api_?key|private_?key|credential)"
)
PLACEHOLDER = re.compile(
    r"(?i)^(|changeme|change_me|replace[-_ ]?me.*|your[-_ ].*|<.*>|\$\{.*\}|xxx+|\*+|example|"
    r"test|testing|dev|development|secret|password|postgres|root|admin|guest|localhost|none|null|"
    r"false|true|todo|dummy|sample|placeholder|default)$"
)


@dataclass(frozen=True)
class SecretHit:
    path: str
    line: int
    kind: str


def find_secrets(path: str, text: str, *, env_file: bool) -> list[SecretHit]:
    hits: list[SecretHit] = []
    for kind, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            hits.append(SecretHit(path, line_of(text, m.start()), kind))
            break  # one finding per kind per file is enough
    if env_file:
        for number, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            value = value.strip().strip("\"'")
            if SENSITIVE_KEY.search(key) and not PLACEHOLDER.match(value) and len(value) >= 8:
                hits.append(SecretHit(path, number, f"value of {key.strip()[:60]}"))
    return hits


def detect_secrets(facts: Facts) -> None:
    snap = facts.snapshot
    for path, text in sorted(snap.files.items()):
        kind = snap.kinds.get(path)
        if kind in {Kind.LOCKFILE, Kind.ENV_EXAMPLE}:
            continue
        for hit in find_secrets(path, text, env_file=kind is Kind.ENV_FILE)[:5]:
            facts.finding(
                "SECRET_COMMITTED",
                Severity.BLOCKER,
                f"Possible {hit.kind} committed in {hit.path} (line {hit.line}).",
                evidence=[facts.evidence(hit.path, f"secret:{hit.kind}"[:255], hit.line)],
                action="Rotate the credential, remove it from the repository (and its history), "
                "and supply it at runtime from a secret store.",
            )
    for path, kind in snap.kinds.items():
        if kind is Kind.ENV_FILE:
            facts.finding(
                "ENV_FILE_COMMITTED",
                Severity.WARNING,
                f"{path} is committed. Environment files usually hold secrets.",
                evidence=[facts.evidence(path, "env_file")],
                action="Add it to .gitignore and commit a .env.example with names only.",
            )
        elif (
            kind is Kind.SECRET_CANDIDATE
            and path.lower().endswith((".pem", ".key"))
            and path not in snap.files
        ):
            facts.finding(
                "KEY_FILE_COMMITTED",
                Severity.WARNING,
                f"{path} looks like a key or certificate file.",
                evidence=[facts.evidence(path, "key_file_name")],
            )


REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Remove every recognizable secret before text leaves the platform (LLM prompts)."""
    out = text
    for pattern in PATTERNS.values():
        out = pattern.sub(REDACTED, out)

    def _assignment(m: re.Match[str]) -> str:
        key, value = m.group(1), m.group(3)
        if SENSITIVE_KEY.search(key) and not PLACEHOLDER.match(value.strip("\"'")):
            return f"{key}{m.group(2)}{REDACTED}"
        return m.group(0)

    return re.sub(r"(?m)^([\w.-]+)(\s*[:=]\s*)(\S+)", _assignment, out)
