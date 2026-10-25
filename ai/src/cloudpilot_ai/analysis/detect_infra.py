"""Container, compose, configuration, environment, port, health and static-site detectors.
Text in, facts out. YAML is parsed with yaml.safe_load only."""

from __future__ import annotations

import posixpath
import re
from typing import Any

import yaml

from cloudpilot_ai.analysis.facts import ConfigKind, Facts, directory_of, line_of
from cloudpilot_ai.analysis.files import Kind, in_non_service_dir
from cloudpilot_ai.contracts import ServiceType, Severity

# image name fragment -> data store engine (compose "image:" services are infrastructure)
IMAGE_STORES = {
    "postgres": "postgresql",
    "postgis": "postgresql",
    "timescale": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "mongo": "mongodb",
    "redis": "redis",
    "valkey": "redis",
    "memcached": "memcached",
    "rabbitmq": "rabbitmq",
    "cp-kafka": "kafka",
    "bitnami/kafka": "kafka",
    "apache/kafka": "kafka",
    "redpanda": "kafka",
    "elasticsearch": "elasticsearch",
    "opensearch": "elasticsearch",
    "minio": "minio",
    "nats": "nats",
    "cassandra": "cassandra",
}
# compose services that only support local development
DEV_TOOL_IMAGES = (
    "zookeeper",
    "kafka-ui",
    "kafdrop",
    "adminer",
    "pgadmin",
    "mailhog",
    "mailpit",
    "localstack",
    "redis-commander",
    "mongo-express",
    "jaeger",
    "prometheus",
    "grafana",
    "zipkin",
    "portainer",
    "traefik",
    "nginx-proxy",
)
BASE_IMAGE_LANGUAGE = {
    "python": "python",
    "node": "javascript",
    "golang": "go",
    "eclipse-temurin": "java",
    "openjdk": "java",
    "amazoncorretto": "java",
    "maven": "java",
    "gradle": "java",
    "ruby": "ruby",
    "php": "php",
    "rust": "rust",
    "mcr.microsoft.com/dotnet": "csharp",
}

HEALTH_ROUTE = re.compile(
    r"""(?:["'`])(/(?:api/)?(?:v\d+/)?(?:health(?:z|check)?|healthy|ready|readyz|livez|ping|status|actuator/health))(?:["'`])"""
)
ENV_REFS = [
    re.compile(r"""os\.(?:environ\.get|getenv)\(\s*["']([A-Z][A-Z0-9_]{1,127})["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]{1,127})["']\s*\]"""),
    re.compile(r"""process\.env\.([A-Z][A-Z0-9_]{1,127})"""),
    re.compile(r"""process\.env\[\s*["']([A-Z][A-Z0-9_]{1,127})["']\s*\]"""),
    re.compile(r"""os\.Getenv\(\s*"([A-Z][A-Z0-9_]{1,127})"\s*\)"""),
    re.compile(r"""System\.getenv\(\s*"([A-Z][A-Z0-9_]{1,127})"\s*\)"""),
    re.compile(r"""\$\{([A-Z][A-Z0-9_]{1,127})(?::[^}]*)?\}"""),  # Spring / compose placeholders
    re.compile(r"""import\.meta\.env\.([A-Z][A-Z0-9_]{1,127})"""),
]
DB_URL_SIGNALS = [
    (
        re.compile(r"sqlite(?:\+\w+)?:///|sqlite3\.connect\(|django\.db\.backends\.sqlite3"),
        "sqlite",
    ),
    (re.compile(r"postgres(?:ql)?(?:\+\w+)?://|django\.db\.backends\.postgresql"), "postgresql"),
    (re.compile(r"mysql(?:\+\w+)?://|django\.db\.backends\.mysql"), "mysql"),
    (re.compile(r"mongodb(?:\+srv)?://"), "mongodb"),
    (re.compile(r"\bredis://"), "redis"),
]
PORT_IN_CODE = [
    re.compile(r"""\.listen\(\s*(?:process\.env\.PORT\s*(?:\|\||\?\?)\s*)?(\d{2,5})"""),
    re.compile(r"""PORT\s*(?:\|\||\?\?|or)\s*["']?(\d{2,5})"""),
    re.compile(r"""\bport\s*=\s*(\d{2,5})\b"""),
    re.compile(r"""(?:--port|-p)\s+(\d{2,5})\b"""),
    re.compile(r"""ListenAndServe\(\s*":(\d{2,5})\""""),
    re.compile(r"""\.Run\(\s*":(\d{2,5})\""""),
]


def _service_for(facts: Facts, path: str, *, create: bool = True):
    """The service whose root contains `path` (deepest match), or a new one at its directory."""
    directory = directory_of(path)
    best = None
    for root, svc in facts.services.items():
        contains = root == "." or directory == root or directory.startswith(root + "/")
        if contains and (best is None or len(root) > len(best.root)):
            best = svc
    if best is not None and (best.root == directory or not create):
        return best
    return facts.service(directory) if create else best


# ───────────────────────── Dockerfile ─────────────────────────
def detect_dockerfiles(facts: Facts) -> None:
    for path in facts.snapshot.of_kind(Kind.DOCKERFILE):
        text = facts.snapshot.files[path]
        facts.config(path, "dockerfile", "dockerfile")
        if in_non_service_dir(path) and not path.startswith(("docker/", "deploy/")):
            continue
        root = directory_of(path)
        if root in {"docker", "deploy", ".docker"}:
            root = "."  # Dockerfiles kept in a docker/ folder usually build the repository root
        svc = facts.service(root)
        svc.dockerfile = svc.dockerfile or path
        svc.add_evidence(facts.evidence(path, "dockerfile"))
        svc.confidence = max(svc.confidence, 0.7)
        stages = re.findall(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", text, re.M | re.I)
        if stages and svc.language is None:
            last = stages[-1].lower()
            for prefix, language in BASE_IMAGE_LANGUAGE.items():
                if prefix in last:
                    svc.language = language
            if any(s in last for s in ("nginx", "httpd", "caddy")) and svc.service_type is None:
                svc.service_type = ServiceType.WEB
                svc.static_site = True
        exposed = re.findall(r"^\s*EXPOSE\s+(\d{2,5})", text, re.M | re.I)
        if exposed:
            line = line_of(text, text.upper().find("EXPOSE"))
            svc.set_port(int(exposed[0]), 0.9, f"EXPOSE in {path}")
            svc.add_evidence(facts.evidence(path, "dockerfile_expose", line))
        cmd = re.findall(r"^\s*(CMD|ENTRYPOINT)\s+(.+)$", text, re.M | re.I)
        if cmd:
            command = cmd[-1][1].strip()
            facts.entry(path, command, 0.9, "dockerfile_cmd")
            svc.entry_command = svc.entry_command or command[:255]
            port = re.search(
                r"(?:--port|-p|--bind\s+[\d.]*:|-b\s+[\d.]*:)[ =]?['\"]?(\d{2,5})", command
            )
            if port:
                svc.set_port(int(port.group(1)), 0.85, f"CMD in {path}")
        if re.search(r"^\s*HEALTHCHECK\s", text, re.M | re.I):
            route = HEALTH_ROUTE.search(text) or re.search(r"(/[\w/-]*health[\w/-]*)", text)
            if route:
                svc.health = svc.health or route.group(1)
        if svc.service_type is None and exposed:
            svc.service_type = ServiceType.API
        # no EXPOSE and no known framework: server or worker is ambiguous -> asked in assemble


# ───────────────────────── Compose ─────────────────────────
def _compose_ports(value: Any) -> list[int]:
    ports: list[int] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and str(item.get("target", "")).isdigit():
            ports.append(int(item["target"]))
            continue
        text = str(item).split("/")[0]
        container = text.rsplit(":", 1)[-1]
        if container.split("-")[0].isdigit():
            ports.append(int(container.split("-")[0]))
    return ports


def _environment_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(k) for k in value]
    if isinstance(value, list):
        return [str(v).split("=", 1)[0] for v in value]
    return []


def detect_compose(facts: Facts) -> None:
    for path in facts.snapshot.of_kind(Kind.COMPOSE):
        text = facts.snapshot.files[path]
        facts.config(path, "compose", "compose")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            facts.finding(
                "INVALID_COMPOSE_FILE",
                Severity.WARNING,
                f"{path} is not valid YAML; it was ignored.",
                evidence=[facts.evidence(path, "compose")],
            )
            continue
        services = data.get("services") if isinstance(data, dict) else None
        if not isinstance(services, dict):
            continue
        base = directory_of(path)
        for name, spec in services.items():
            if not isinstance(spec, dict):
                continue
            line = line_of(text, text.find(f"{name}:"))
            ev = facts.evidence(path, "compose_service", line)
            for key in _environment_keys(spec.get("environment")):
                facts.env(key, path)
            build = spec.get("build")
            image = str(spec.get("image") or "").lower()
            if build:
                context = (
                    build
                    if isinstance(build, str)
                    else (build.get("context") or ".")
                    if isinstance(build, dict)
                    else "."
                )
                root = (
                    posixpath.normpath(posixpath.join(base, str(context)))
                    if base != "."
                    else posixpath.normpath(str(context))
                )
                if root.startswith(".."):
                    continue
                svc = facts.service(root or ".", default_name=str(name))
                svc.compose_name = str(name)[:255]
                if svc.name in {facts.repo_name, posixpath.basename(svc.root)}:
                    svc.name = str(name)[:255]
                svc.add_evidence(ev)
                svc.confidence = max(svc.confidence, 0.8)
                for port in _compose_ports(spec.get("ports") or spec.get("expose")):
                    svc.set_port(port, 0.8, f"ports in {path}")
                    break
                if isinstance(build, dict) and build.get("dockerfile"):
                    svc.dockerfile = svc.dockerfile or posixpath.normpath(
                        posixpath.join(root, str(build["dockerfile"]))
                    )
                continue
            if any(tool in image for tool in DEV_TOOL_IMAGES):
                continue
            for fragment, engine in IMAGE_STORES.items():
                if fragment in image:
                    facts.data_store(engine, f"image {image[:80]} in {path}", 0.95, ev)
                    break
            else:
                if image:
                    facts.finding(
                        "PREBUILT_IMAGE_SERVICE",
                        Severity.INFO,
                        f"Compose service '{name}' runs the prebuilt image {image[:80]}; it is "
                        "listed as a dependency, not a service CloudPilot builds.",
                        evidence=[ev],
                    )


# ───────────────────────── environment variables ─────────────────────────
def detect_env(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.ENV_EXAMPLE, Kind.ENV_FILE):
        facts.config(path, "env_example", "env_file")
        for raw in snap.files[path].splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].removeprefix("export ").strip()
            facts.env(key, path)
    scanned = snap.of_kind(Kind.SOURCE, Kind.ENTRY, Kind.APP_CONFIG, Kind.DOCKERFILE)
    for path in scanned:
        text = snap.files[path]
        for pattern in ENV_REFS:
            for name in pattern.findall(text):
                facts.env(name, path)


# ───────────────────────── ports, health routes, app config ─────────────────────────
def detect_code_signals(facts: Facts) -> None:
    snap = facts.snapshot
    for path in snap.of_kind(Kind.SOURCE, Kind.ENTRY, Kind.PLATFORM, Kind.APP_CONFIG):
        text = snap.files[path]
        for pattern, engine in DB_URL_SIGNALS:
            m = pattern.search(text)
            if m:
                ev = facts.evidence(path, "database_url", line_of(text, m.start()))
                facts.data_store(engine, f"database configuration in {path}", 0.85, ev)
        svc = _service_for(facts, path, create=False)
        if svc is None:
            continue
        if path.endswith("schema.prisma"):
            provider = re.search(
                r'provider\s*=\s*"(postgresql|mysql|mongodb|sqlite|cockroachdb)"', text
            )
            if provider:
                engine = {"cockroachdb": "postgresql"}.get(provider.group(1), provider.group(1))
                facts.data_store(
                    engine,
                    f"Prisma datasource in {path}",
                    0.95,
                    facts.evidence(path, "prisma_schema"),
                )
            continue
        name = path.rsplit("/", 1)[-1]
        if name.startswith("application.") or name.startswith("bootstrap."):
            port = re.search(r"server\.port\s*[=:]\s*(\d{2,5})", text) or re.search(
                r"^server:\s*\n(?:\s+.*\n)*?\s+port:\s*\$?\{?(?:[A-Z_]+:)?(\d{2,5})", text, re.M
            )
            if port:
                svc.set_port(int(port.group(1)), 0.9, f"server.port in {path}")
                svc.add_evidence(facts.evidence(path, "spring_config", line_of(text, port.start())))
            continue
        if name == "Procfile":
            web = re.search(r"^web:\s*(.+)$", text, re.M)
            if web:
                facts.entry(path, web.group(1).strip(), 0.9, "procfile")
                svc.entry_command = svc.entry_command or web.group(1).strip()[:255]
            continue
        for pattern in PORT_IN_CODE:
            m = pattern.search(text)
            if m and 80 <= int(m.group(1)) < 65536:
                svc.set_port(int(m.group(1)), 0.7, f"listen call in {path}")
                svc.add_evidence(facts.evidence(path, "port_in_code", line_of(text, m.start())))
                break
        route = HEALTH_ROUTE.search(text)
        if route and svc.health is None:
            svc.health = route.group(1)
            svc.add_evidence(facts.evidence(path, "health_route", line_of(text, route.start())))
        if snap.kinds.get(path) is Kind.ENTRY:
            facts.entry(path, None, 0.6, "entry_file")


# ───────────────────────── static sites ─────────────────────────
STATIC_DIRS = (".", "public", "site", "www", "docs", "static")


def detect_static(facts: Facts) -> None:
    snap = facts.snapshot
    for path in sorted(snap.of_kind(Kind.STATIC_INDEX), key=lambda p: p.count("/")):
        root = directory_of(path)
        if root not in STATIC_DIRS:
            continue
        servers = [s for s in facts.services.values() if not s.static_site]
        if servers:
            return  # a server application serves its own HTML
        svc = facts.service(".", default_name=facts.repo_name)
        svc.static_site = True
        svc.service_type = ServiceType.WEB
        svc.language = svc.language or "html"
        svc.framework = svc.framework or "static HTML"
        svc.framework_kind = "frontend"
        svc.confidence = max(svc.confidence, 0.85)
        svc.add_evidence(facts.evidence(path, "static_index"))
        svc.entry_command = None
        facts.entry(path, None, 0.85, "static_index")
        return


# ───────────────────────── config files (CI, IaC, k8s, platforms) ─────────────────────────
CONFIG_KINDS: dict[Kind, ConfigKind] = {
    Kind.CI: "ci",
    Kind.TERRAFORM: "terraform",
    Kind.K8S: "k8s",
    Kind.PLATFORM: "other",
    Kind.LOCKFILE: "build",
}


def detect_config_files(facts: Facts) -> None:
    for path, kind in sorted(facts.snapshot.kinds.items()):
        mapped = CONFIG_KINDS.get(kind)
        if mapped:
            facts.config(path, mapped, f"{kind.value}_file")
