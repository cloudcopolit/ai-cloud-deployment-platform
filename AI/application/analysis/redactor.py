from __future__ import annotations

import re
from pathlib import PurePosixPath

DEFAULT_MAX_CHARS = 20_000

# Patterns that must never reach an LLM prompt, tool output, or log.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # AWS Access Key IDs
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "<REDACTED_AWS_KEY>"),
    # GitHub tokens
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), "<REDACTED_GITHUB_TOKEN>"),
    # Private keys
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        "<REDACTED_PRIVATE_KEY>",
    ),
    # Generic Bearer / API key assignments in config or code
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret)"
            r"(\s*[:=]\s*['\"])([^'\"\r\n]{6,})(['\"])"
        ),
        r"\1\2<REDACTED>\4",
    ),
    # Connection string credentials (e.g. postgres://user:pass@host/db)
    (
        re.compile(r"([a-zA-Z0-9+.-]+://[^:/@\s]+:)([^@\s]+)(@)"),
        r"\1<REDACTED>\3",
    ),
)

_ENV_LINE_RE = re.compile(r"^(\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=)(.*)$")


def is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name == ".env" or name.startswith(".env.")


def redact_env_content(text: str) -> str:
    """Keep only environment variable names from .env or .env.* files; redact all values."""
    redacted_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            redacted_lines.append(line)
            continue
        match = _ENV_LINE_RE.match(line)
        if match:
            prefix, raw_val = match.groups()
            val_clean = raw_val.strip().strip("'\"")
            if val_clean == "":
                redacted_lines.append(f"{prefix}")
            else:
                redacted_lines.append(f"{prefix}<REDACTED>")
        else:
            redacted_lines.append("# <REDACTED_LINE>")
    return "\n".join(redacted_lines)


def redact_secrets(text: str, *, path: str = "") -> str:
    """Scrub secret values from file content before exposing it to the LLM."""
    if path and is_env_file(path):
        return redact_env_content(text)

    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def format_with_line_numbers(
    text: str,
    *,
    path: str = "",
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Redact secrets, bound size, and prepend 1-based line numbers for Evidence citations."""
    bounded = text[:max_chars]
    redacted = redact_secrets(bounded, path=path)
    lines = redacted.splitlines()
    numbered = "\n".join(f"{idx}: {line}" for idx, line in enumerate(lines, start=1))
    if len(text) > max_chars:
        numbered += f"\n... [truncated after {max_chars} chars]"
    return numbered
