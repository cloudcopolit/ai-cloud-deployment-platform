"""Manifest detectors per ecosystem. Manifests are parsed as data (tomllib, json, bounded
regular expressions); nothing from the repository is imported or executed."""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any, Literal

from cloudpilot_ai.analysis.facts import Facts, directory_of, line_of
from cloudpilot_ai.analysis.files import Kind, in_non_service_dir
from cloudpilot_ai.contracts import Dependency, ServiceType, Severity

Ecosystem = Literal[
    "pypi", "npm", "maven", "gradle", "go", "cargo", "nuget", "rubygems", "composer", "other"
]

# dependency name -> (display name, framework kind, default port, service type)
PY_FRAMEWORKS: dict[str, tuple[str, str, int | None, ServiceType]] = {
    "fastapi": ("FastAPI", "backend", 8000, ServiceType.API),
    "flask": ("Flask", "backend", 5000, ServiceType.API),
    "django": ("Django", "fullstack", 8000, ServiceType.WEB),
    "starlette": ("Starlette", "backend", 8000, ServiceType.API),
    "litestar": ("Litestar", "backend", 8000, ServiceType.API),
    "aiohttp": ("aiohttp", "backend", 8080, ServiceType.API),
    "tornado": ("Tornado", "backend", 8888, ServiceType.API),
    "sanic": ("Sanic", "backend", 8000, ServiceType.API),
    "quart": ("Quart", "backend", 5000, ServiceType.API),
    "streamlit": ("Streamlit", "frontend", 8501, ServiceType.WEB),
    "gradio": ("Gradio", "frontend", 7860, ServiceType.WEB),
    "celery": ("Celery", "worker", None, ServiceType.WORKER),
    "dramatiq": ("Dramatiq", "worker", None, ServiceType.WORKER),
    "rq": ("RQ", "worker", None, ServiceType.WORKER),
}
PY_STORES = {
    "psycopg": "postgresql",
    "psycopg2": "postgresql",
    "psycopg2-binary": "postgresql",
    "asyncpg": "postgresql",
    "pg8000": "postgresql",
    "mysqlclient": "mysql",
    "pymysql": "mysql",
    "aiomysql": "mysql",
    "mysql-connector-python": "mysql",
    "pymongo": "mongodb",
    "motor": "mongodb",
    "mongoengine": "mongodb",
    "beanie": "mongodb",
    "redis": "redis",
    "aioredis": "redis",
    "kafka-python": "kafka",
    "confluent-kafka": "kafka",
    "aiokafka": "kafka",
    "pika": "rabbitmq",
    "aio-pika": "rabbitmq",
    "elasticsearch": "elasticsearch",
    "opensearch-py": "elasticsearch",
    "cassandra-driver": "cassandra",
    "pymemcache": "memcached",
    "nats-py": "nats",
}
NODE_FRAMEWORKS: dict[str, tuple[str, str, int | None, ServiceType | None]] = {
    "next": ("Next.js", "fullstack", 3000, ServiceType.WEB),
    "nuxt": ("Nuxt", "fullstack", 3000, ServiceType.WEB),
    "@remix-run/node": ("Remix", "fullstack", 3000, ServiceType.WEB),
    "@sveltejs/kit": ("SvelteKit", "fullstack", 3000, ServiceType.WEB),
    "astro": ("Astro", "frontend", 4321, ServiceType.WEB),
    "@nestjs/core": ("NestJS", "backend", 3000, ServiceType.API),
    "express": ("Express", "backend", 3000, ServiceType.API),
    "fastify": ("Fastify", "backend", 3000, ServiceType.API),
    "koa": ("Koa", "backend", 3000, ServiceType.API),
    "@hapi/hapi": ("hapi", "backend", 3000, ServiceType.API),
    "react": ("React", "frontend", None, None),
    "vue": ("Vue", "frontend", None, None),
    "@angular/core": ("Angular", "frontend", None, None),
    "svelte": ("Svelte", "frontend", None, None),
    "gatsby": ("Gatsby", "frontend", None, None),
}
NODE_STATIC_BUILDERS = {"vite", "react-scripts", "@angular/cli", "gatsby", "parcel", "webpack"}
NODE_STORES = {
    "pg": "postgresql",
    "pg-promise": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mysql2": "mysql",
    "mongoose": "mongodb",
    "mongodb": "mongodb",
    "redis": "redis",
    "ioredis": "redis",
    "bull": "redis",
    "bullmq": "redis",
    "kafkajs": "kafka",
    "amqplib": "rabbitmq",
    "@elastic/elasticsearch": "elasticsearch",
    "nats": "nats",
    "memjs": "memcached",
    "@aws-sdk/client-sqs": "sqs",
    "@aws-sdk/client-dynamodb": "dynamodb",
}
JVM_STORES = {
    "postgresql": "postgresql",
    "r2dbc-postgresql": "postgresql",
    "mysql-connector-java": "mysql",
    "mysql-connector-j": "mysql",
    "mariadb-java-client": "mariadb",
    "spring-boot-starter-data-mongodb": "mongodb",
    "spring-boot-starter-data-mongodb-reactive": "mongodb",
    "spring-boot-starter-data-redis": "redis",
    "spring-boot-starter-data-redis-reactive": "redis",
    "spring-kafka": "kafka",
    "kafka-clients": "kafka",
    "spring-cloud-starter-stream-kafka": "kafka",
    "spring-boot-starter-amqp": "rabbitmq",
    "spring-boot-starter-data-elasticsearch": "elasticsearch",
    "spring-boot-starter-data-cassandra": "cassandra",
}
GO_FRAMEWORKS = {
    "github.com/gin-gonic/gin": "Gin",
    "github.com/labstack/echo": "Echo",
    "github.com/gofiber/fiber": "Fiber",
    "github.com/go-chi/chi": "chi",
    "github.com/gorilla/mux": "gorilla/mux",
}
GO_STORES = {
    "github.com/lib/pq": "postgresql",
    "github.com/jackc/pgx": "postgresql",
    "github.com/go-sql-driver/mysql": "mysql",
    "go.mongodb.org/mongo-driver": "mongodb",
    "github.com/redis/go-redis": "redis",
    "github.com/go-redis/redis": "redis",
    "github.com/segmentio/kafka-go": "kafka",
    "github.com/IBM/sarama": "kafka",
    "github.com/Shopify/sarama": "kafka",
    "github.com/confluentinc/confluent-kafka-go": "kafka",
    "github.com/rabbitmq/amqp091-go": "rabbitmq",
    "github.com/streadway/amqp": "rabbitmq",
    "github.com/nats-io/nats.go": "nats",
}

_PEP508 = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;#]*)")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _service_root_allowed(facts: Facts, path: str) -> bool:
    return not in_non_service_dir(path)


def _add_dep(
    facts: Facts, ecosystem: Ecosystem, name: str, spec: str | None, manifest: str, dev: bool
) -> None:
    if len(facts.dependencies) >= 2000 or not name:
        return
    facts.dependencies.append(
        Dependency(
            ecosystem=ecosystem,
            name=name[:255],
            version_spec=((spec or None) and spec.strip()[:255]) or None,
            dev_only=dev,
            manifest_path=manifest,
        )
    )


# ───────────────────────── Python ─────────────────────────
def _python_requirements(text: str) -> list[tuple[str, str, int]]:
    out = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http:", "https:", "file:")):
            continue
        m = _PEP508.match(line)
        if m:
            out.append((m.group(1), m.group(3).strip(), i))
    return out


def _pep508(spec: str) -> tuple[str, str]:
    m = _PEP508.match(spec)
    return (m.group(1), m.group(3).strip()) if m else (spec, "")


def detect_python(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.MANIFEST):
        name = path.rsplit("/", 1)[-1]
        text = snap.files[path]
        deps: list[tuple[str, str, int | None, bool]] = []
        if name.lower().startswith("requirements"):
            dev = bool(re.search(r"(dev|test|lint|doc)", name.lower()))
            deps = [(n, s, ln, dev) for n, s, ln in _python_requirements(text)]
            if not dev and deps and all("==" not in s for _, s, _, _ in deps):
                facts.finding(
                    "UNPINNED_DEPENDENCIES",
                    Severity.WARNING,
                    f"{path} pins no exact versions; builds are not reproducible.",
                    evidence=[facts.evidence(path, "python_requirements")],
                    action="Pin versions (pip-compile, uv lock, or name==version).",
                )
        elif name == "pyproject.toml":
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError:
                continue
            project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
            for spec in project.get("dependencies", []) or []:
                if isinstance(spec, str):
                    n, s = _pep508(spec)
                    deps.append((n, s, None, False))
            for group in (project.get("optional-dependencies") or {}).values():
                for spec in group if isinstance(group, list) else []:
                    if isinstance(spec, str):
                        n, s = _pep508(spec)
                        deps.append((n, s, None, True))
            poetry = (
                data.get("tool", {}).get("poetry", {}) if isinstance(data.get("tool"), dict) else {}
            )
            for n, s in (poetry.get("dependencies") or {}).items():
                if n.lower() != "python":
                    deps.append((n, s if isinstance(s, str) else "", None, False))
            for group in (poetry.get("group") or {}).values():
                for n, s in (group.get("dependencies") or {}).items():
                    deps.append((n, s if isinstance(s, str) else "", None, True))
            if not deps and "build-system" in data and "project" not in data:
                continue
        elif name == "Pipfile":
            try:
                data = tomllib.loads(text)
            except tomllib.TOMLDecodeError:
                continue
            for section, dev in (("packages", False), ("dev-packages", True)):
                for n, s in (data.get(section) or {}).items():
                    deps.append((n, s if isinstance(s, str) else "", None, dev))
        elif name == "setup.py":
            block = re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S)
            for spec in re.findall(r"['\"]([^'\"]+)['\"]", block.group(1) if block else ""):
                n, s = _pep508(spec)
                deps.append((n, s, None, False))
        else:
            continue
        if not deps:
            continue
        _python_service(facts, path, deps)


def _python_service(
    facts: Facts, manifest: str, deps: list[tuple[str, str, int | None, bool]]
) -> None:
    root = directory_of(manifest)
    best: tuple[str, str, int | None, ServiceType] | None = None
    for name, spec, line, dev in deps:
        _add_dep(facts, "pypi", name, spec, manifest, dev)
        key = _norm(name)
        ev = facts.evidence(manifest, "python_manifest", line)
        if key in PY_FRAMEWORKS and not dev:
            display, kind, port, stype = PY_FRAMEWORKS[key]
            facts.framework(display, kind, _version(spec), 0.95, ev)
            if best is None or (best[3] is ServiceType.WORKER and stype is not ServiceType.WORKER):
                best = (display, kind, port, stype)
        if key in PY_STORES and not dev:
            facts.data_store(PY_STORES[key], f"{name} in {manifest}", 0.9, ev)
        if key == "sqlalchemy" and not dev:
            facts.framework("SQLAlchemy", "other", _version(spec), 0.9, ev)
    if best is None or not _service_root_allowed(facts, manifest):
        return
    svc = facts.service(root)
    svc.language = svc.language or "python"
    svc.framework, svc.framework_kind, svc.service_type = best[0], best[1], best[3]
    svc.manifest = svc.manifest or manifest
    svc.confidence = max(svc.confidence, 0.85)
    svc.add_evidence(facts.evidence(manifest, "python_manifest"))
    if best[2]:
        svc.set_port(best[2], 0.4, f"{best[0]} default")


def _version(spec: str | None) -> str | None:
    if not spec:
        return None
    m = re.search(r"(\d+(?:\.\d+){0,3})", spec)
    return m.group(1) if m else None


# ───────────────────────── Node.js ─────────────────────────
def detect_node(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.MANIFEST):
        if not path.endswith("package.json"):
            continue
        try:
            data = json.loads(snap.files[path])
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        root = directory_of(path)
        if data.get("workspaces"):
            facts.workspace_roots.add(root)
        deps: dict[str, Any] = data.get("dependencies") or {}
        dev_deps: dict[str, Any] = data.get("devDependencies") or {}
        if not isinstance(deps, dict) or not isinstance(dev_deps, dict):
            continue
        for name, spec in deps.items():
            _add_dep(facts, "npm", name, str(spec), path, False)
        for name, spec in dev_deps.items():
            _add_dep(facts, "npm", name, str(spec), path, True)
        text = snap.files[path]
        found: tuple[str, str, int | None, ServiceType | None] | None = None
        for name in list(deps) + list(dev_deps):
            line = line_of(text, text.find(f'"{name}"'))
            ev = facts.evidence(path, "package_json", line)
            spec = str(deps.get(name) or dev_deps.get(name) or "")
            if name in NODE_FRAMEWORKS:
                display, kind, port, stype = NODE_FRAMEWORKS[name]
                facts.framework(display, kind, _version(spec), 0.95, ev)
                rank = {"fullstack": 3, "backend": 2, "frontend": 1}.get(kind, 0)
                current = (
                    {"fullstack": 3, "backend": 2, "frontend": 1}.get(found[1], 0) if found else -1
                )
                if rank > current:
                    found = (display, kind, port, stype)
            if name in NODE_STORES and name in deps:
                facts.data_store(NODE_STORES[name], f"{name} in {path}", 0.9, ev)
            if name in {"@prisma/client", "prisma"}:
                facts.framework("Prisma", "other", _version(spec), 0.9, ev)
        raw_scripts = data.get("scripts")
        scripts: dict[str, Any] = raw_scripts if isinstance(raw_scripts, dict) else {}
        start = str(scripts.get("start") or "")
        is_server_script = bool(
            re.search(r"\b(node|nest|next start|nuxt start|ts-node|tsx)\b", start)
        )
        if not _service_root_allowed(facts, path):
            continue
        if found is None and not is_server_script:
            continue
        runnable = any(k in scripts for k in ("start", "start:prod", "serve", "dev"))
        if found is not None and found[3] is not None and not runnable:
            continue  # e.g. a shared library that depends on NestJS: built, never started
        svc = facts.service(root, default_name=_pkg_name(data.get("name")))
        svc.language = svc.language or (
            "typescript" if "typescript" in dev_deps or "typescript" in deps else "javascript"
        )
        svc.manifest = svc.manifest or path
        svc.add_evidence(facts.evidence(path, "package_json"))
        if found:
            svc.framework, svc.framework_kind = found[0], found[1]
            if found[3] is not None:
                svc.service_type = found[3]
                if found[2]:
                    svc.set_port(found[2], 0.4, f"{found[0]} default")
            else:  # SPA: built to static files
                svc.service_type = ServiceType.WEB
                svc.static_site = True
                svc.needs_build = True
        else:
            svc.service_type = ServiceType.API
        svc.confidence = max(svc.confidence, 0.85 if found else 0.6)
        if start:
            facts.entry(path, f"npm start  ({start[:200]})", 0.8, "package_json_scripts")
            port_flag = re.search(r"(?:-p|--port)[ =](\d{2,5})", start)
            if port_flag:
                svc.set_port(int(port_flag.group(1)), 0.85, "start script")
        lock = any(
            snap.exists(f"{'' if root == '.' else root + '/'}{n}")
            for n in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb")
        )
        if not lock and not any(
            snap.exists(f"{r}/{n}" if r != "." else n)
            for r in facts.workspace_roots
            for n in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml")
        ):
            facts.finding(
                "NO_LOCKFILE",
                Severity.WARNING,
                f"{path} has no lockfile next to it; installs are not reproducible.",
                evidence=[facts.evidence(path, "package_json")],
                action="Commit package-lock.json, yarn.lock or pnpm-lock.yaml.",
            )


def _pkg_name(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.rsplit("/", 1)[-1]


# ───────────────────────── JVM ─────────────────────────
def detect_jvm(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.MANIFEST):
        name = path.rsplit("/", 1)[-1]
        if name not in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            continue
        text = snap.files[path]
        ecosystem: Ecosystem = "maven" if name == "pom.xml" else "gradle"
        if ecosystem == "maven":
            artifacts = re.findall(r"<artifactId>\s*([\w.\-]+)\s*</artifactId>", text)
            boot = re.search(
                r"<parent>.*?spring-boot-starter-parent.*?<version>\s*([\w.\-]+)\s*</version>",
                text,
                re.S,
            )
            boot_version = boot.group(1) if boot else None
            is_module_parent = "<modules>" in text
        else:
            artifacts = re.findall(r"['\"][\w.\-]+:([\w.\-]+)(?::[\w.\-]+)?['\"]", text)
            boot = re.search(
                r"org\.springframework\.boot['\"]?\)?\s*version\s*['\"]([\w.\-]+)", text
            )
            boot_version = boot.group(1) if boot else None
            is_module_parent = False
        for artifact in sorted(set(artifacts))[:300]:
            _add_dep(facts, ecosystem, artifact, None, path, "test" in artifact)
            if artifact in JVM_STORES:
                ev = facts.evidence(path, "jvm_build", line_of(text, text.find(artifact)))
                facts.data_store(JVM_STORES[artifact], f"{artifact} in {path}", 0.9, ev)
        web = any(
            a in artifacts for a in ("spring-boot-starter-web", "spring-boot-starter-webflux")
        )
        quarkus = any(a.startswith("quarkus-") for a in artifacts)
        if not (web or quarkus or "spring-boot-starter" in " ".join(artifacts)) or is_module_parent:
            continue
        if not _service_root_allowed(facts, path):
            continue
        display = "Quarkus" if quarkus else "Spring Boot"
        ev = facts.evidence(path, "jvm_build")
        facts.framework(display, "backend", boot_version, 0.95, ev)
        svc = facts.service(directory_of(path))
        svc.language = svc.language or ("kotlin" if path.endswith(".kts") else "java")
        svc.framework, svc.framework_kind = display, "backend"
        svc.service_type = ServiceType.API if (web or quarkus) else ServiceType.WORKER
        svc.manifest = svc.manifest or path
        svc.confidence = max(svc.confidence, 0.85)
        svc.add_evidence(ev)
        if web or quarkus:
            svc.set_port(8080, 0.4, f"{display} default")
        if "spring-boot-starter-actuator" in artifacts:
            svc.health = svc.health or "/actuator/health"


# ───────────────────────── Go ─────────────────────────
def detect_go(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.MANIFEST):
        if not path.endswith("go.mod"):
            continue
        text = snap.files[path]
        requires = re.findall(
            r"^\s*(?:require\s+)?([\w.\-/]+\.[\w.\-/]+)\s+(v[\w.\-+]+)", text, re.M
        )
        framework = None
        for module, version in requires[:500]:
            _add_dep(facts, "go", module, version, path, False)
            ev = facts.evidence(path, "go_mod", line_of(text, text.find(module)))
            for prefix, display in GO_FRAMEWORKS.items():
                if module.startswith(prefix):
                    framework = display
                    facts.framework(display, "backend", version.lstrip("v"), 0.9, ev)
            for prefix, engine in GO_STORES.items():
                if module.startswith(prefix):
                    facts.data_store(engine, f"{module} in {path}", 0.9, ev)
        if not _service_root_allowed(facts, path):
            continue
        root = directory_of(path)
        has_main = any(
            p.endswith("main.go") and (p == "main.go" if root == "." else p.startswith(root + "/"))
            for p in snap.kinds
        )
        if not has_main and framework is None:
            continue
        svc = facts.service(root)
        svc.language = svc.language or "go"
        svc.framework = svc.framework or framework
        svc.framework_kind = "backend"
        svc.service_type = svc.service_type or ServiceType.API
        svc.manifest = svc.manifest or path
        svc.confidence = max(svc.confidence, 0.8 if framework else 0.6)
        svc.add_evidence(facts.evidence(path, "go_mod"))


# ───────────────────────── other ecosystems ─────────────────────────
OTHER_MANIFESTS = {
    "Gemfile": (
        "ruby",
        "rubygems",
        {"rails": ("Ruby on Rails", 3000), "sinatra": ("Sinatra", 4567)},
    ),
    "composer.json": (
        "php",
        "composer",
        {"laravel/framework": ("Laravel", 8000), "symfony/framework-bundle": ("Symfony", 8000)},
    ),
    "Cargo.toml": (
        "rust",
        "cargo",
        {"actix-web": ("Actix Web", 8080), "axum": ("Axum", 3000), "rocket": ("Rocket", 8000)},
    ),
    "mix.exs": ("elixir", "other", {"phoenix": ("Phoenix", 4000)}),
}


def detect_other(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.MANIFEST):
        name = path.rsplit("/", 1)[-1]
        if name not in OTHER_MANIFESTS or not _service_root_allowed(facts, path):
            continue
        language, ecosystem, frameworks = OTHER_MANIFESTS[name]
        text = snap.files[path]
        for dep, (display, port) in frameworks.items():
            index = text.find(dep)
            if index < 0:
                continue
            ev = facts.evidence(path, f"{ecosystem}_manifest", line_of(text, index))
            facts.framework(display, "backend", None, 0.8, ev)
            _add_dep(facts, ecosystem, dep, None, path, False)  # type: ignore[arg-type]
            svc = facts.service(directory_of(path))
            svc.language = svc.language or language
            svc.framework = display
            svc.framework_kind = "backend"
            svc.service_type = svc.service_type or ServiceType.API
            svc.manifest = path
            svc.confidence = max(svc.confidence, 0.75)
            svc.add_evidence(ev)
            svc.set_port(port, 0.35, f"{display} default")
            break
    for path in sorted(p for p in snap.kinds if p.endswith(".csproj")):
        if in_non_service_dir(path):
            continue
        svc = facts.service(directory_of(path))
        svc.language = svc.language or "csharp"
        svc.framework = svc.framework or ".NET"
        svc.service_type = svc.service_type or ServiceType.API
        svc.confidence = max(svc.confidence, 0.6)
        svc.add_evidence(facts.evidence(path, "csproj"))
