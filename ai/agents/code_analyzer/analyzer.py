"""Deterministic, non-executing analysis of Python source code."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

FileStatus = Literal["parsed", "syntax_error", "skipped"]
AnalysisStatus = Literal["completed", "partial", "failed", "no_supported_files"]


@dataclass(frozen=True, slots=True)
class ImportFact:
    """An import statement found in a source file."""

    module: str | None
    names: tuple[str, ...]
    line: int
    kind: Literal["import", "from_import"]
    level: int = 0


@dataclass(frozen=True, slots=True)
class DefinitionFact:
    """A class or callable definition found in a source file."""

    name: str
    kind: Literal["class", "function", "async_function"]
    line: int
    end_line: int
    decorators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    """Analysis result for one supplied source file."""

    path: str
    status: FileStatus
    imports: tuple[ImportFact, ...] = ()
    definitions: tuple[DefinitionFact, ...] = ()
    has_main_guard: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Aggregated analysis results across supplied source files."""

    status: AnalysisStatus
    files: tuple[FileAnalysis, ...]
    total_files: int
    parsed_files: int
    syntax_error_files: int
    skipped_files: int


def _valid_relative_path(path: str) -> bool:
    """Reject paths that are absolute or attempt directory traversal."""
    if not path or "\\" in path:
        return False

    candidate = PurePosixPath(path)
    return (
        not candidate.is_absolute()
        and ".." not in candidate.parts
        and ":" not in candidate.parts[0]
    )


def _is_main_guard(node: ast.AST) -> bool:
    """Recognize `if __name__ == '__main__':` in either operand order."""
    if not isinstance(node, ast.If):
        return False

    test = node.test
    if not isinstance(test, ast.Compare):
        return False

    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False

    if len(test.comparators) != 1:
        return False

    left, right = test.left, test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def _analyze_parsed_file(path: str, tree: ast.Module) -> FileAnalysis:
    imports: list[ImportFact] = []
    definitions: list[DefinitionFact] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.append(
                ImportFact(
                    module=None,
                    names=tuple(alias.name for alias in node.names),
                    line=node.lineno,
                    kind="import",
                )
            )
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                ImportFact(
                    module=node.module,
                    names=tuple(alias.name for alias in node.names),
                    line=node.lineno,
                    kind="from_import",
                    level=node.level,
                )
            )

        if isinstance(node, ast.ClassDef):
            kind = "class"
        elif isinstance(node, ast.AsyncFunctionDef):
            kind = "async_function"
        elif isinstance(node, ast.FunctionDef):
            kind = "function"
        else:
            continue

        definitions.append(
            DefinitionFact(
                name=node.name,
                kind=kind,
                line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                decorators=tuple(ast.unparse(item) for item in node.decorator_list),
            )
        )

    imports.sort(key=lambda item: item.line)
    definitions.sort(key=lambda item: item.line)

    return FileAnalysis(
        path=path,
        status="parsed",
        imports=tuple(imports),
        definitions=tuple(definitions),
        has_main_guard=any(_is_main_guard(node) for node in ast.walk(tree)),
    )


def analyze_python_sources(
    sources: Mapping[str, str],
    *,
    max_files: int = 200,
    max_source_bytes: int = 1_000_000,
    max_total_source_bytes: int = 10_000_000,
) -> AnalysisReport:
    """Analyze supplied Python source without executing it.

    Files are processed in sorted path order for deterministic results.
    Invalid paths, unsupported files, and resource-limit violations are
    reported as skipped. A syntax error in one file does not stop others.
    """
    if min(max_files, max_source_bytes, max_total_source_bytes) < 1:
        raise ValueError("All resource limits must be positive.")

    results: list[FileAnalysis] = []
    supported_paths = sorted(
        path
        for path in sources
        if isinstance(path, str) and path.lower().endswith(".py")
    )

    for path in sorted(sources):
        if not isinstance(path, str) or not path.lower().endswith(".py"):
            results.append(
                FileAnalysis(
                    path=str(path), status="skipped", error="Unsupported file type."
                )
            )
        elif not _valid_relative_path(path):
            results.append(
                FileAnalysis(
                    path=path, status="skipped", error="Invalid relative file path."
                )
            )

    valid_paths = [path for path in supported_paths if _valid_relative_path(path)]
    total_bytes = 0

    for index, path in enumerate(valid_paths):
        if index >= max_files:
            results.append(
                FileAnalysis(
                    path=path, status="skipped", error="File-count limit exceeded."
                )
            )
            continue

        source = sources[path]
        if not isinstance(source, str):
            results.append(
                FileAnalysis(
                    path=path, status="skipped", error="Source must be a string."
                )
            )
            continue

        try:
            source_bytes = len(source.encode("utf-8"))
        except UnicodeEncodeError:
            results.append(
                FileAnalysis(
                    path=path, status="skipped", error="Source is not valid UTF-8 text."
                )
            )
            continue

        if source_bytes > max_source_bytes:
            results.append(
                FileAnalysis(
                    path=path, status="skipped", error="Per-file size limit exceeded."
                )
            )
            continue

        if total_bytes + source_bytes > max_total_source_bytes:
            results.append(
                FileAnalysis(
                    path=path,
                    status="skipped",
                    error="Total source size limit exceeded.",
                )
            )
            continue

        total_bytes += source_bytes

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            results.append(
                FileAnalysis(
                    path=path,
                    status="syntax_error",
                    error=f"Line {exc.lineno}: {exc.msg}",
                )
            )
            continue

        results.append(_analyze_parsed_file(path, tree))

    results.sort(key=lambda item: item.path)
    parsed = sum(item.status == "parsed" for item in results)
    syntax_errors = sum(item.status == "syntax_error" for item in results)
    skipped = sum(item.status == "skipped" for item in results)

    if not supported_paths:
        status: AnalysisStatus = "no_supported_files"
    elif parsed == 0 and syntax_errors > 0:
        status = "failed"
    elif syntax_errors > 0 or skipped > 0:
        status = "partial"
    else:
        status = "completed"

    return AnalysisReport(
        status=status,
        files=tuple(results),
        total_files=len(results),
        parsed_files=parsed,
        syntax_error_files=syntax_errors,
        skipped_files=skipped,
    )
