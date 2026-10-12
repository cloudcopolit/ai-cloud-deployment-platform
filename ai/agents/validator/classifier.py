"""Rule-based error classification parser for test and execution diagnostics."""

from __future__ import annotations

import re

from agents.validator.models import ErrorCategory

# Compiled regex patterns ordered by classification specificity
_PATTERNS: tuple[tuple[ErrorCategory, re.Pattern[str]], ...] = (
    (
        ErrorCategory.TIMEOUT,
        re.compile(
            r"(?:TimeoutExpired|Command timed out|Operation timed out|Deadline exceeded)",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorCategory.BUILD_ERROR,
        re.compile(
            r"(?:SyntaxError:|IndentationError:|TabError:|invalid syntax)",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorCategory.CONFIG_ERROR,
        re.compile(
            r"(?:ValidationError|pydantic_core\._pydantic_core\.ValidationError|"
            r"SettingsError|ConfigurationError|Field required|missing environment variable|"
            r"KeyError:\s*['\"][A-Z0-9_]+['\"])",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorCategory.DEPENDENCY_ERROR,
        re.compile(
            r"(?:ModuleNotFoundError:\s*No module named|"
            r"ImportError:\s*cannot import name|"
            r"ImportError:\s*DLL load failed|"
            r"Could not find a version that satisfies the requirement|"
            r"No matching distribution found for|"
            r"pip\s+install.*failed|ResolutionImpossible)",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorCategory.RUNTIME_CRASH,
        re.compile(
            r"(?:ConnectionRefusedError|Address already in use|"
            r"WinError\s*10048|Errno\s*48|Errno\s*98|"
            r"OperationalError.*could not connect to server|"
            r"psycopg2|asyncpg|sqlalchemy\.exc\.OperationalError|"
            r"Fatal Python error|Unhandled exception|Process exited prematurely)",
            re.IGNORECASE,
        ),
    ),
    (
        ErrorCategory.TEST_FAILURE,
        re.compile(
            r"(?:AssertionError|FAILED\s+[^\n]+::|assert\s+.+==|"
            r"FixtureLookupError|pytest\.fail|Tests failed)",
            re.IGNORECASE,
        ),
    ),
)


def classify_error(output: str, exit_code: int | None = None) -> ErrorCategory:
    """Classify an error message or command output into a standardized ErrorCategory."""
    if not output:
        return (
            ErrorCategory.RUNTIME_CRASH
            if exit_code is not None and exit_code != 0
            else ErrorCategory.TEST_FAILURE
        )

    for category, pattern in _PATTERNS:
        if pattern.search(output):
            return category

    # Default fallbacks based on context
    if exit_code is not None and exit_code != 0:
        return ErrorCategory.RUNTIME_CRASH
    return ErrorCategory.TEST_FAILURE


def extract_primary_error_message(text: str) -> str:
    """Extract a concise single-line description of the leading error or traceback exception."""
    if not text:
        return "Unknown error occurred"

    # Search for standard Python exception lines: `ExceptionClass: message`
    exception_match = re.search(
        r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning):\s*.+)$",
        text,
        re.MULTILINE,
    )
    if exception_match:
        return exception_match.group(1).strip()

    # Search for pytest failure summary line
    failure_match = re.search(r"^FAILED\s+(.+)$", text, re.MULTILINE)
    if failure_match:
        return failure_match.group(0).strip()

    # Search for timeout line
    timeout_match = re.search(r"\[TIMEOUT\].+", text)
    if timeout_match:
        return timeout_match.group(0).strip()

    # Otherwise return the last non-empty line of the output
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[-1]

    return "Execution failed"
