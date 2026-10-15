#!/usr/bin/env python3
"""Check that relative links and anchors in Markdown files resolve.

Validates Markdown links/images and HTML href/src/srcset attributes that point
inside the repository, including `#anchor` fragments against GitHub-style
heading slugs. External URLs are not fetched. Code blocks and inline code are
ignored.

Usage: python .github/scripts/check_markdown_links.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_ATTR = re.compile(r"\b(?:href|src|srcset)=\"([^\"]+)\"")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
HTML_ANCHOR = re.compile(r"<a\s+[^>]*(?:id|name)=\"([^\"]+)\"")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)


def markdown_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [Path(line) for line in output.splitlines() if Path(line).is_file()]


def strip_code(text: str) -> str:
    return INLINE_CODE.sub("", FENCE.sub("", text))


def slugify(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading)  # inline HTML
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> text
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        text = strip_code(path.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        found = set(HTML_ANCHOR.findall(text))
        for heading in HEADING.findall(text):
            slug = slugify(heading)
            count = seen.get(slug, 0)
            found.add(slug if count == 0 else f"{slug}-{count}")
            seen[slug] = count + 1
        cache[path] = found
    return cache[path]


def targets(text: str) -> list[str]:
    found = MD_LINK.findall(text)
    for value in HTML_ATTR.findall(text):
        found.extend(part.split()[0] for part in value.split(",") if part.strip())
    return found


def main() -> int:
    root = Path.cwd()
    cache: dict[Path, set[str]] = {}
    errors = 0
    files = markdown_files()
    for source in files:
        for target in targets(strip_code(source.read_text(encoding="utf-8"))):
            if EXTERNAL.match(target):
                continue
            path_part, _, fragment = unquote(target).partition("#")
            if path_part:
                base = root if path_part.startswith("/") else source.parent
                resolved = (base / path_part.lstrip("/")).resolve()
            else:
                resolved = source.resolve()
            problem = None
            if not resolved.exists():
                problem = "target does not exist"
            elif (
                fragment
                and resolved.suffix == ".md"
                and fragment.lower() not in anchors(resolved.relative_to(root), cache)
            ):
                problem = f"no heading or anchor named '#{fragment}'"
            if problem:
                errors += 1
                print(f"::error file={source.as_posix()}::Broken link '{target}': {problem}")

    print(f"Checked {len(files)} Markdown files; {errors} broken link(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
