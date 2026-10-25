"""Which repository files matter, and how to classify them. Pure functions over paths."""

from __future__ import annotations

import posixpath
import re
from enum import StrEnum

SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "bower_components",
        "vendor",
        "dist",
        "build",
        "out",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "target",
        "bin",
        "obj",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        "site-packages",
        "coverage",
        ".gradle",
        ".idea",
        ".vscode",
        ".terraform",
        "Pods",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        "storybook-static",
    }
)

# Directories whose manifests describe tooling or examples, not deployable services.
NON_SERVICE_DIRS = frozenset(
    {
        "test",
        "tests",
        "__tests__",
        "e2e",
        "examples",
        "example",
        "docs",
        "doc",
        "fixtures",
        "samples",
        "sample",
        "scripts",
        ".github",
        ".devcontainer",
        "benchmarks",
    }
)

BINARY_EXT = frozenset(
    [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".tiff",
        ".svgz",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        ".ear",
        ".class",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".bin",
        ".o",
        ".a",
        ".pyc",
        ".pyo",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".mov",
        ".avi",
        ".webm",
        ".wav",
        ".ogg",
        ".flac",
        ".psd",
        ".ai",
        ".sketch",
        ".fig",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".parquet",
        ".pkl",
        ".h5",
        ".onnx",
        ".pt",
        ".npy",
        ".keystore",
        ".jks",
        ".p12",
        ".pfx",
    ]
)

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".rs": "rust",
    ".swift": "swift",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".less": "css",
    ".vue": "vue",
    ".svelte": "svelte",
    ".sh": "shell",
    ".tf": "hcl",
}

SOURCE_LANGUAGES = frozenset(
    {"python", "javascript", "typescript", "java", "kotlin", "go", "ruby", "php", "csharp", "rust"}
)


class Kind(StrEnum):
    MANIFEST = "manifest"
    LOCKFILE = "lockfile"
    DOCKERFILE = "dockerfile"
    COMPOSE = "compose"
    ENV_EXAMPLE = "env_example"
    ENV_FILE = "env_file"  # a real .env committed to the repository
    CI = "ci"
    TERRAFORM = "terraform"
    K8S = "k8s"
    PLATFORM = "platform"  # Procfile, vercel.json, fly.toml, serverless.yml, …
    APP_CONFIG = "app_config"  # application.properties/yml, next.config.*, …
    ENTRY = "entry"
    STATIC_INDEX = "static_index"
    SECRET_CANDIDATE = "secret_candidate"  # noqa: S105 - a file kind, not a password
    INSTRUCTIONS = "instructions"  # README, AGENTS.md, ...: data, never instructions to us
    SOURCE = "source"
    OTHER = "other"


MANIFESTS = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "Pipfile",
        "setup.cfg",
        "setup.py",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "Cargo.toml",
        "Gemfile",
        "composer.json",
        "mix.exs",
        "pubspec.yaml",
    }
)
LOCKFILES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "go.sum",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "gradle.lockfile",
    }
)
PLATFORM_FILES = frozenset(
    {
        "Procfile",
        "app.json",
        "vercel.json",
        "netlify.toml",
        "fly.toml",
        "render.yaml",
        "app.yaml",
        "serverless.yml",
        "serverless.yaml",
        "template.yaml",
        "amplify.yml",
        "nginx.conf",
    }
)
ENTRY_NAMES = frozenset(
    {
        "main.py",
        "app.py",
        "wsgi.py",
        "asgi.py",
        "manage.py",
        "server.py",
        "run.py",
        "__main__.py",
        "server.js",
        "server.ts",
        "app.js",
        "app.ts",
        "index.js",
        "index.ts",
        "main.js",
        "main.ts",
        "main.go",
    }
)
APP_CONFIG_PREFIXES = (
    "application.properties",
    "application.yml",
    "application.yaml",
    "bootstrap.yml",
    "next.config.",
    "vite.config.",
    "nuxt.config.",
    "astro.config.",
    "svelte.config.",
    "angular.json",
    "settings.py",
    "nest-cli.json",
    "schema.prisma",
)
SECRET_NAME = re.compile(
    r"(^id_(rsa|dsa|ecdsa|ed25519)$|\.(pem|key|tfvars)$|^credentials(\.\w+)?$|"
    r"^secrets?\.(json|ya?ml|env|txt)$|^\.(npmrc|pypirc|netrc|htpasswd)$|^service-account.*\.json$)",
    re.IGNORECASE,
)
COMPOSE_NAME = re.compile(r"^(docker-)?compose([.-][\w-]+)?\.ya?ml$")
ENV_EXAMPLE = re.compile(
    r"^(\.env\.(example|sample|template|dist|defaults)|example\.env|\.env\.\w+\.example)$"
)
ENV_FILE = re.compile(r"^\.env(\.(local|dev|development|prod|production|staging|test))?$")
INSTRUCTION_NAMES = frozenset({"readme.md", "agents.md", "claude.md", ".cursorrules", "readme"})


def parts(path: str) -> list[str]:
    return path.split("/")


def is_skipped(path: str) -> bool:
    """Generated, vendored or binary content: never read, not counted as source."""
    segments = parts(path)
    if any(s in SKIP_DIRS for s in segments[:-1]):
        return True
    return posixpath.splitext(segments[-1])[1].lower() in BINARY_EXT


def in_non_service_dir(path: str) -> bool:
    return any(s.lower() in NON_SERVICE_DIRS for s in parts(path)[:-1])


def classify(path: str) -> Kind:
    name = parts(path)[-1]
    lower = name.lower()
    directory = posixpath.dirname(path)
    if name in MANIFESTS:
        return Kind.MANIFEST
    if name in LOCKFILES:
        return Kind.LOCKFILE
    if re.match(r"^requirements([._-][\w-]+)?\.(txt|in)$", lower):
        return Kind.MANIFEST
    if name == "Dockerfile" or lower.startswith("dockerfile") or lower.endswith(".dockerfile"):
        return Kind.DOCKERFILE
    if COMPOSE_NAME.match(lower):
        return Kind.COMPOSE
    if ENV_EXAMPLE.match(lower):
        return Kind.ENV_EXAMPLE
    if ENV_FILE.match(lower):
        return Kind.ENV_FILE
    if (
        (directory.startswith(".github/workflows") and lower.endswith((".yml", ".yaml")))
        or lower
        in {
            ".gitlab-ci.yml",
            "jenkinsfile",
            "azure-pipelines.yml",
            "bitbucket-pipelines.yml",
        }
        or path == ".circleci/config.yml"
    ):
        return Kind.CI
    if lower.endswith(".tf"):
        return Kind.TERRAFORM
    if lower.endswith((".yaml", ".yml")) and any(
        s in {"k8s", "kubernetes", "helm", "charts", "manifests"} for s in parts(directory)
    ):
        return Kind.K8S
    if name in PLATFORM_FILES:
        return Kind.PLATFORM
    if lower.startswith(APP_CONFIG_PREFIXES):
        return Kind.APP_CONFIG
    if SECRET_NAME.search(lower):
        return Kind.SECRET_CANDIDATE
    if lower in INSTRUCTION_NAMES:
        return Kind.INSTRUCTIONS
    if name in ENTRY_NAMES or re.match(r"^\w+Application\.(java|kt)$", name):
        return Kind.ENTRY
    if lower == "index.html":
        return Kind.STATIC_INDEX
    if LANGUAGE_BY_EXT.get(posixpath.splitext(lower)[1]) in SOURCE_LANGUAGES:
        return Kind.SOURCE
    return Kind.OTHER


# Lower number = read first when the read budget is tight.
READ_PRIORITY = {
    Kind.MANIFEST: 0,
    Kind.DOCKERFILE: 0,
    Kind.COMPOSE: 0,
    Kind.ENV_EXAMPLE: 1,
    Kind.ENV_FILE: 1,
    Kind.PLATFORM: 1,
    Kind.APP_CONFIG: 1,
    Kind.SECRET_CANDIDATE: 1,
    Kind.ENTRY: 2,
    Kind.STATIC_INDEX: 2,
    Kind.CI: 3,
    Kind.TERRAFORM: 3,
    Kind.K8S: 4,
    Kind.SOURCE: 5,
}
