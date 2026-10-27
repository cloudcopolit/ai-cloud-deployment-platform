"""Facts -> AnalysisReport: resolve services, apply the user's answers, decide blockers and
missing information, and recommend a deployment method with its reasoning."""

from __future__ import annotations

import posixpath
from collections import Counter

from cloudpilot_ai.analysis.facts import Facts, ServiceCandidate
from cloudpilot_ai.analysis.files import LANGUAGE_BY_EXT, in_non_service_dir
from cloudpilot_ai.contracts import (
    AnalysisMeta,
    AnalysisReport,
    DeploymentRecommendation,
    DetectedService,
    Framework,
    Language,
    RepositoryRef,
    ServiceType,
    Severity,
)

ANALYZER_VERSION = "cloudpilot-analyzer/0.3.0"
# Stacks CloudPilot can plan for (ADR-022). Anything else is reported, not guessed.
PLANNABLE_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "java",
    "kotlin",
    "go",
    "ruby",
    "php",
    "csharp",
    "rust",
    "html",
}
# Data stores the automated container archetype provisions itself (managed PostgreSQL).
AUTOMATED_STORES = {"postgresql"}
DISPLAY = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "memcached": "Memcached",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "elasticsearch": "Elasticsearch/OpenSearch",
    "minio": "MinIO (S3-compatible)",
    "nats": "NATS",
    "cassandra": "Cassandra",
    "sqlite": "SQLite",
    "s3": "S3",
    "sqs": "SQS",
    "dynamodb": "DynamoDB",
}


def _resolve_services(facts: Facts) -> list[ServiceCandidate]:
    kept: list[ServiceCandidate] = []
    for root, svc in sorted(facts.services.items()):
        if (
            root in facts.workspace_roots
            and svc.framework is None
            and (svc.dockerfile is None or svc.dockerfile in facts.shared_dockerfiles)
        ):
            continue  # a monorepo root: its package.json only holds workspaces and its
            # Dockerfile (if any) is the shared one each service builds
        if svc.service_type is None and svc.dockerfile is None and not svc.static_site:
            continue
        if (
            root != "."
            and in_non_service_dir(root + "/x")
            and svc.compose_name is None
            and svc.dockerfile is None
        ):
            continue
        kept.append(svc)
    # A root Dockerfile next to sub-services usually builds one of them; keep it only if it
    # is the only thing at the root and nothing else claims it.
    names: Counter[str] = Counter()
    for svc in kept:
        base = svc.name or "app"
        names[base] += 1
        if names[base] > 1:
            svc.name = f"{base}-{names[base]}"[:255]
    return kept


def _apply_answers(facts: Facts, services: list[ServiceCandidate], answers: dict[str, str]) -> None:
    for svc in services:
        value = answers.get(f"port:{svc.name}", "").strip().lower()
        if value.isdigit() and 0 < int(value) < 65536:
            svc.set_port(int(value), 1.0, "answered by the user")
            if svc.service_type is None:
                svc.service_type = ServiceType.API
        elif value in {"none", "worker", "no"} and svc.service_type in {None, ServiceType.WORKER}:
            svc.service_type = ServiceType.WORKER


def _languages(facts: Facts) -> list[Language]:
    total = sum(facts.snapshot.language_bytes.values()) or 1
    out = []
    for name, size in facts.snapshot.language_bytes.most_common(12):
        share = round(100 * size / total, 1)
        if share < 1:
            continue
        sample = next(
            (
                p
                for p in sorted(facts.snapshot.kinds)
                if LANGUAGE_BY_EXT.get(posixpath.splitext(p)[1].lower()) == name
            ),
            None,
        )
        out.append(
            Language(
                name=name,
                share_percent=share,
                confidence=0.95,
                evidence=[facts.evidence(sample, "file_extensions")] if sample else [],
            )
        )
    return out


def _recommend(facts: Facts, services: list[ServiceCandidate]) -> DeploymentRecommendation:
    stores = sorted(facts.data_stores)
    runnable = [
        s
        for s in services
        if s.service_type in {ServiceType.API, ServiceType.WEB, ServiceType.WORKER}
    ]
    if not runnable:
        return DeploymentRecommendation(
            method="unsupported",
            reasoning="No runnable service was found (no web framework, server start script, "
            "Dockerfile or static index.html), so there is nothing to deploy yet.",
            automated_by_cloudpilot=False,
            confidence=0.6,
        )
    servers = [s for s in runnable if not s.static_site]
    if not servers:
        needs_build = [s.name for s in runnable if s.needs_build]
        reasons = [
            "Only static front-end content was found; S3 static website hosting (with "
            "CloudFront on real AWS) serves it without servers."
        ]
        if needs_build:
            reasons.append(
                f"{', '.join(needs_build)} must be built first (npm run build). CloudPilot "
                "does not run repository code yet, so this deployment is not automated."
            )
        return DeploymentRecommendation(
            method="static_site",
            reasoning=" ".join(reasons)[:1000],
            services=[s.name for s in runnable][:50],
            automated_by_cloudpilot=not needs_build,
            confidence=0.85,
        )
    reasons = []
    automated = True
    if len(servers) > 1:
        automated = False
        reasons.append(
            f"{len(servers)} services were found ({', '.join(s.name for s in servers[:8])}"
            f"{'…' if len(servers) > 8 else ''}). Each runs as its own container service; "
            "CloudPilot automates single-service deployments only, so this plan needs manual "
            "completion."
        )
    else:
        reasons.append(
            f"One {servers[0].framework or servers[0].language or 'container'} service "
            f"({servers[0].name}) runs well as a container on ECS Fargate behind a load balancer."
        )
    missing_docker = [s.name for s in servers if not s.dockerfile]
    if missing_docker:
        automated = False
        reasons.append(
            f"No Dockerfile for {', '.join(missing_docker[:8])}; CloudPilot does not generate "
            "Dockerfiles yet."
        )
    extra = [DISPLAY.get(e, e) for e in stores if e not in AUTOMATED_STORES]
    if extra:
        automated = False
        reasons.append(
            f"Needs {', '.join(extra)}, which the automated archetype does not provision "
            "(it provisions managed PostgreSQL only)."
        )
    elif "postgresql" in stores:
        reasons.append("PostgreSQL maps to Amazon RDS.")
    return DeploymentRecommendation(
        method="container",
        reasoning=" ".join(reasons)[:1000],
        services=[s.name for s in servers][:50],
        automated_by_cloudpilot=automated,
        confidence=0.8 if automated else 0.7,
    )


def _summary(facts: Facts, services: list[ServiceCandidate], rec: DeploymentRecommendation) -> str:
    if not services:
        return "No deployable service was detected."
    stacks = Counter(
        f"{(s.language or '?').capitalize()}/{s.framework}"
        if s.framework
        else (s.language or "container").capitalize()
        for s in services
    )
    stack_text = ", ".join(f"{n} x {k}" if n > 1 else k for k, n in stacks.most_common(6))
    head = (
        f"Monorepo with {len(services)} services ({stack_text})"
        if len(services) > 1
        else f"{stack_text} application"
    )
    parts = [head]
    if facts.data_stores:
        parts.append(
            "data stores: " + ", ".join(DISPLAY.get(e, e) for e in sorted(facts.data_stores))
        )
    tooling = [
        k
        for k, flag in (
            ("Docker Compose", any(c.kind == "compose" for c in facts.config_files)),
            ("CI", any(c.kind == "ci" for c in facts.config_files)),
            ("Terraform", any(c.kind == "terraform" for c in facts.config_files)),
            ("Kubernetes manifests", any(c.kind == "k8s" for c in facts.config_files)),
        )
        if flag
    ]
    if tooling:
        parts.append(", ".join(tooling) + " present")
    parts.append(f"recommended: {rec.method.replace('_', ' ')}")
    return ("; ".join(parts) + ".")[:1000]


def assemble(
    facts: Facts,
    *,
    repository: RepositoryRef,
    answers: dict[str, str],
    duration_ms: int,
    model: str | None,
) -> AnalysisReport:
    services = _resolve_services(facts)
    _apply_answers(facts, services, answers)

    if not services:
        facts.finding(
            "NO_DEPLOYABLE_SERVICE",
            Severity.BLOCKER,
            "No runnable service was found: no web framework, start script, Dockerfile or "
            "static site.",
            action="Point CloudPilot at the directory that contains the application.",
        )

    for svc in services:
        runnable_http = (
            svc.service_type in {ServiceType.API, ServiceType.WEB} and not svc.static_site
        )
        if runnable_http and svc.port is None:
            facts.ask(
                f"port:{svc.name}",
                f"Which port does the service '{svc.name}' ({svc.root}) listen on?",
            )
        if svc.service_type is None and not svc.static_site:
            facts.ask(
                f"port:{svc.name}",
                f"Does '{svc.name}' ({svc.root}) accept HTTP requests? Answer its port, or 'none' "
                "if it is a background worker.",
            )
        if runnable_http and svc.health is None:
            facts.finding(
                "NO_HEALTH_ENDPOINT",
                Severity.WARNING,
                f"No health-check route was found for '{svc.name}'.",
                evidence=svc.evidence[:1],
                action="Add a lightweight GET /health route so the load balancer can check it.",
            )
        if not svc.static_site and svc.dockerfile is None and svc.service_type is not None:
            facts.finding(
                "NO_DOCKERFILE",
                Severity.WARNING,
                f"'{svc.name}' has no Dockerfile; a container deployment needs one.",
                evidence=svc.evidence[:1],
                action="Add a Dockerfile. CloudPilot does not generate Dockerfiles yet.",
            )
        if svc.language and svc.language not in PLANNABLE_LANGUAGES and svc.dockerfile is None:
            facts.unsupported_tech(
                svc.language,
                f"'{svc.name}' is written in {svc.language} and has no Dockerfile; CloudPilot can "
                "only plan it when it ships as a container.",
            )

    server_dbs = {"postgresql", "mysql", "mariadb", "mongodb", "cassandra", "dynamodb"}
    if "sqlite" in facts.data_stores and server_dbs & set(facts.data_stores):
        sqlite = facts.data_stores.pop("sqlite")
        facts.finding(
            "SQLITE_DEV_FALLBACK",
            Severity.INFO,
            "SQLite is used next to a server database, presumably for local development; "
            "it is not part of the deployment.",
            evidence=list(sqlite.evidence),
        )
    stores = set(facts.data_stores)
    if "sqlite" in stores and not stores - {"sqlite", "s3", "minio"}:
        choice = answers.get("datastore:sqlite", "").strip().lower()
        if choice in {"postgresql", "keep"}:
            facts.finding(
                "SQLITE_PRIMARY_DATABASE",
                Severity.WARNING,
                "SQLite is the only database. "
                + (
                    "You chose managed PostgreSQL instead."
                    if choice == "postgresql"
                    else "You chose to keep it: its data is lost whenever a container is replaced."
                ),
            )
        else:
            facts.finding(
                "REQUIRES_LOCAL_ONLY_RESOURCE",
                Severity.BLOCKER,
                "SQLite is the only database; container file systems are not durable.",
                evidence=list(facts.data_stores["sqlite"].evidence),
                action="Answer whether to use managed PostgreSQL instead, then re-run the "
                "analysis.",
            )
            facts.ask(
                "datastore:sqlite",
                "SQLite data does not survive container restarts. Use managed PostgreSQL "
                "('postgresql') or keep SQLite and accept data loss ('keep')?",
            )

    if facts.snapshot.truncated:
        facts.finding(
            "ANALYSIS_TRUNCATED",
            Severity.INFO,
            f"Only part of the repository was read ({len(facts.snapshot.files)} of "
            f"{facts.snapshot.listed} files); results may be incomplete.",
        )

    recommendation = _recommend(facts, services)
    confidences = [s.confidence for s in services] or [0.3]
    overall = sum(confidences) / len(confidences) * (0.85 if facts.snapshot.truncated else 1.0)

    detected = [
        DetectedService(
            name=s.name,
            service_type=s.service_type or ServiceType.OTHER,
            language=s.language,
            framework=s.framework,
            path=s.root,
            port=s.port,
            has_dockerfile=s.dockerfile is not None,
            health_endpoint=s.health,
            metadata={
                "port_source": s.port_source,
                "port_confidence": round(s.port_confidence, 2),
                "dockerfile": s.dockerfile,
                "static_site": s.static_site,
                "needs_build": s.needs_build,
                "compose_service": s.compose_name,
                "start_command": s.entry_command,
            },
            confidence=round(min(1.0, s.confidence), 2),
            evidence=s.evidence[:10],
        )
        for s in services[:50]
    ]
    frameworks = [
        Framework(
            name=h.name,
            version=h.version,
            kind=h.kind
            if h.kind in {"backend", "frontend", "fullstack", "worker", "test"}
            else "other",  # type: ignore[arg-type]
            confidence=round(h.confidence, 2),
            evidence=h.evidence[:10],
        )
        for h in sorted(facts.frameworks.values(), key=lambda h: h.name)[:100]
    ]
    return AnalysisReport(
        repository=repository,
        summary=_summary(facts, services, recommendation),
        languages=_languages(facts),
        frameworks=frameworks,
        services=detected,
        dependencies=facts.dependencies[:2000],
        config_files=facts.config_files[:200],
        entry_points=facts.entry_points[:100],
        data_stores=[facts.data_stores[k] for k in sorted(facts.data_stores)][:50],
        env_vars=[facts.env_vars[k] for k in sorted(facts.env_vars)][:500],
        blockers=facts.blockers[:100],
        warnings=facts.warnings[:200],
        missing_info=facts.missing[:50],
        unsupported=facts.unsupported[:50],
        recommendation=recommendation,
        overall_confidence=round(min(1.0, overall), 2),
        meta=AnalysisMeta(
            analyzer_version=ANALYZER_VERSION,
            files_scanned=len(facts.snapshot.files),
            files_skipped=facts.snapshot.skipped,
            truncated=facts.snapshot.truncated,
            duration_ms=duration_ms,
            model=model,
        ),
    )
