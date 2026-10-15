#!/usr/bin/env python3
"""Fail if any JSON, YAML, or TOML file in the repository cannot be parsed.

Covers configuration, prompt, schema, and workflow definition files anywhere
in the repository (including everything under ai/), so new files are checked
without registering them. tsconfig*.json files are skipped because they are
JSON-with-comments and are validated by the TypeScript compiler instead.

Usage: python .github/scripts/validate_structured_files.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from fnmatch import fnmatch
from pathlib import Path

import yaml

SKIP = ("**/tsconfig*.json", "tsconfig*.json")


class YamlLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):  # type: ignore[misc]
    """Safe loader that accepts application-specific tags such as Compose's `!reset`."""


def _untagged(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


YamlLoader.add_multi_constructor("!", _untagged)


def repository_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [Path(line) for line in output.splitlines() if Path(line).is_file()]


def parse(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        json.loads(text)
    elif path.suffix in {".yml", ".yaml"}:
        for _ in yaml.load_all(text, Loader=YamlLoader):
            pass
    elif path.suffix == ".toml":
        tomllib.loads(text)


def main() -> int:
    checked = 0
    failures = []
    for path in repository_files():
        if path.suffix not in {".json", ".yml", ".yaml", ".toml"}:
            continue
        if any(fnmatch(path.as_posix(), pattern) for pattern in SKIP):
            continue
        checked += 1
        try:
            parse(path)
        except (ValueError, yaml.YAMLError, UnicodeDecodeError) as error:
            failures.append(path)
            message = str(error).replace("\n", " ")
            print(f"::error file={path.as_posix()}::Invalid {path.suffix[1:].upper()}: {message}")

    print(f"Checked {checked} structured files; {len(failures)} invalid.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
