"""Archetype "container-postgres": one HTTP service with a Dockerfile, plus PostgreSQL, on ECS
Fargate behind an Application Load Balancer (ADR-023/024).

Deterministic: the same report always gives the same plan. Every size is the smallest that
works, every price comes from the generated AWS price table, and every quantity that is a guess
(traffic, log volume) is stated as an assumption.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from cloudpilot_ai.architecture.pricing import PriceTable, monthly
from cloudpilot_ai.contracts import (
    AnalysisReport,
    ArchitecturePlan,
    Assumption,
    Component,
    ComponentType,
    CostEstimate,
    CostLine,
    DetectedService,
    Finding,
    Impact,
    SecurityDesign,
    ServiceType,
    Severity,
)

ARCHETYPE = "container-postgres"

# Sizing (ADR-024): the smallest Fargate task and RDS instance; one of each.
TASK_CPU = 256  # 0.25 vCPU
TASK_MEMORY = 512  # MiB
DESIRED_COUNT = 1
DB_INSTANCE_CLASS = "db.t4g.micro"
DB_ENGINE_VERSION = "16"
DB_STORAGE_GB = 20
LOG_RETENTION_DAYS = 7
PUBLIC_IPV4_ADDRESSES = 3  # load balancer in two AZs + one task
ALB_AVERAGE_LCU = 0.5
LOG_GB_PER_MONTH = 1.0

HTTP_TYPES = {ServiceType.API, ServiceType.WEB}
# Variables the deployment provides itself (ADR-024): the database connection.
PROVIDED_ENV = ["DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "PORT"]


@dataclass(frozen=True)
class Eligibility:
    service: DetectedService | None
    reasons: list[str]

    @property
    def ok(self) -> bool:
        return self.service is not None and not self.reasons


def eligibility(report: AnalysisReport) -> Eligibility:
    """Why this report does (not) fit the archetype. Reasons are shown to the user."""
    reasons: list[str] = []
    if report.blockers:
        reasons.append(f"the analysis has {len(report.blockers)} blocker(s)")
    method = report.recommendation.method if report.recommendation else None
    if method not in (None, "container"):
        reasons.append(f"the recommended deployment is {method}, not a container")
    http = [s for s in report.services if s.service_type in HTTP_TYPES]
    if len(http) != 1:
        reasons.append(f"it needs exactly one HTTP service; found {len(http)}")
    service = http[0] if len(http) == 1 else None
    if service is not None:
        if not service.has_dockerfile:
            reasons.append(f"service {service.name} has no Dockerfile")
        if service.port is None:
            reasons.append(f"the port of service {service.name} is unknown")
    engines = sorted({d.engine for d in report.data_stores})
    if "postgresql" not in engines:
        reasons.append("it needs PostgreSQL; none was detected")
    others = [e for e in engines if e != "postgresql"]
    if others:
        reasons.append(f"other data stores are not automated yet: {', '.join(others)}")
    return Eligibility(service, reasons)


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:40] or "app"
    return slug if slug[0].isalpha() else f"app-{slug}"[:40]


def design(
    report: AnalysisReport,
    service: DetectedService,
    *,
    source_analysis_id: UUID,
    prices: PriceTable,
) -> ArchitecturePlan:
    assert service.port is not None  # noqa: S101 - eligibility() guarantees it
    app_id = _slug(service.name)
    health = service.health_endpoint or "/"
    env_names = sorted(
        {e.name for e in report.env_vars if e.name not in PROVIDED_ENV and e.required}
    )[:30]

    components = [
        Component(
            id="vpc",
            type=ComponentType.VPC,
            config={
                "cidr": "10.42.0.0/16",
                "availability_zones": 2,
                "public_subnets": 2,
                "private_subnets": 2,
                "nat_gateway": False,
            },
            rationale=(
                "A dedicated VPC across two Availability Zones: public subnets for the load "
                "balancer and the task, private subnets for the database. No NAT gateway: the "
                "task pulls its image over its public IP, the database needs no internet."
            ),
        ),
        Component(
            id="alb",
            type=ComponentType.ALB,
            depends_on=["vpc"],
            config={
                "scheme": "internet-facing",
                "listener": "HTTP:80",
                "health_check_path": health,
                "ingress": "only the CIDR you allow at deploy time",
            },
            rationale=(
                f"An Application Load Balancer is the public entry point; it checks {health} on "
                f"the task and only forwards healthy traffic to port {service.port}."
            ),
        ),
        Component(
            id="db",
            type=ComponentType.RDS,
            depends_on=["vpc"],
            config={
                "engine": "postgres",
                "engine_version": DB_ENGINE_VERSION,
                "instance_class": DB_INSTANCE_CLASS,
                "storage_gb": DB_STORAGE_GB,
                "storage_type": "gp3",
                "multi_az": False,
                "publicly_accessible": False,
                "storage_encrypted": True,
            },
            rationale=(
                "The analysis found PostgreSQL, so a managed RDS PostgreSQL instance in the "
                "private subnets; only the application's security group can reach port 5432."
            ),
        ),
        Component(
            id="secrets",
            type=ComponentType.SECRETS_MANAGER,
            depends_on=["db"],
            config={"holds": ["DATABASE_URL", "DB_PASSWORD"], "generated": True},
            rationale=(
                "The database password is generated at deploy time and kept in Secrets Manager; "
                "the task receives DATABASE_URL and DB_PASSWORD from it, never as plain text."
            ),
        ),
        Component(
            id=app_id,
            type=ComponentType.ECS_SERVICE,
            serves_service=service.name,
            depends_on=["alb", "vpc", "db", "secrets"],
            config={
                "launch_type": "FARGATE",
                "cpu": TASK_CPU,
                "memory": TASK_MEMORY,
                "desired_count": DESIRED_COUNT,
                "container_port": service.port,
                "health_path": health,
                "image": "supplied at deploy time, pinned by digest",
                "assign_public_ip": True,
                "env_names": env_names,
                "service_path": service.path,
            },
            rationale=(
                f"Service {service.name} ({service.framework or service.language or 'container'}) "
                f"has a Dockerfile and listens on port {service.port}, so it runs as one Fargate "
                "task (0.25 vCPU, 0.5 GB) that accepts traffic only from the load balancer."
            ),
        ),
        Component(
            id="logs",
            type=ComponentType.CLOUDWATCH,
            depends_on=[app_id],
            config={"log_group_retention_days": LOG_RETENTION_DAYS},
            rationale="The task's stdout and stderr go to a CloudWatch log group kept for 7 days.",
        ),
    ]

    p = prices
    vcpu = TASK_CPU / 1024 * DESIRED_COUNT
    gb = TASK_MEMORY / 1024 * DESIRED_COUNT
    lines = [
        CostLine(
            component_id=app_id,
            monthly_usd=round(
                monthly(p["fargate_vcpu_hour"], vcpu, hourly=True)
                + monthly(p["fargate_gb_hour"], gb, hourly=True),
                2,
            ),
            basis=(
                f"{DESIRED_COUNT} Fargate task: {vcpu:g} vCPU x ${p['fargate_vcpu_hour'].usd}/h + "
                f"{gb:g} GB x ${p['fargate_gb_hour'].usd}/h, 730 h"
            ),
        ),
        CostLine(
            component_id="alb",
            monthly_usd=round(
                monthly(p["alb_hour"], 1, hourly=True)
                + monthly(p["alb_lcu_hour"], ALB_AVERAGE_LCU, hourly=True),
                2,
            ),
            basis=(
                f"1 ALB x ${p['alb_hour'].usd}/h + {ALB_AVERAGE_LCU} LCU x "
                f"${p['alb_lcu_hour'].usd}/LCU-h, 730 h"
            ),
        ),
        CostLine(
            component_id="vpc",
            monthly_usd=monthly(p["public_ipv4_hour"], PUBLIC_IPV4_ADDRESSES, hourly=True),
            basis=(
                f"{PUBLIC_IPV4_ADDRESSES} in-use public IPv4 addresses (ALB in 2 AZs + 1 task) "
                f"x ${p['public_ipv4_hour'].usd}/h, 730 h; no NAT gateway"
            ),
        ),
        CostLine(
            component_id="db",
            monthly_usd=round(
                monthly(p["rds_postgres_t4g_micro_hour"], 1, hourly=True)
                + monthly(p["rds_gp3_gb_month"], DB_STORAGE_GB, hourly=False),
                2,
            ),
            basis=(
                f"{DB_INSTANCE_CLASS} Single-AZ x ${p['rds_postgres_t4g_micro_hour'].usd}/h, "
                f"730 h + {DB_STORAGE_GB} GB gp3 x ${p['rds_gp3_gb_month'].usd}/GB-month"
            ),
        ),
        CostLine(
            component_id="secrets",
            monthly_usd=monthly(p["secretsmanager_secret_month"], 1, hourly=False),
            basis=f"1 secret x ${p['secretsmanager_secret_month'].usd}/month",
        ),
        CostLine(
            component_id="logs",
            monthly_usd=round(
                monthly(p["cloudwatch_logs_ingest_gb"], LOG_GB_PER_MONTH, hourly=False)
                + monthly(p["cloudwatch_logs_storage_gb_month"], LOG_GB_PER_MONTH, hourly=False),
                2,
            ),
            basis=(
                f"{LOG_GB_PER_MONTH:g} GB ingested x ${p['cloudwatch_logs_ingest_gb'].usd}/GB + "
                f"{LOG_GB_PER_MONTH:g} GB stored x "
                f"${p['cloudwatch_logs_storage_gb_month'].usd}/GB-month"
            ),
        ),
    ]
    total = round(sum(line.monthly_usd for line in lines), 2)

    return ArchitecturePlan(
        source_analysis_id=source_analysis_id,
        region=p.region,
        archetype=ARCHETYPE,
        automated=True,
        components=components,
        assumptions=[
            Assumption(
                statement="Monthly figures assume 730 hours of uptime and on-demand prices.",
                impact=Impact.LOW,
            ),
            Assumption(
                statement=(
                    f"Light traffic: {ALB_AVERAGE_LCU} load-balancer capacity units on average "
                    f"and {LOG_GB_PER_MONTH:g} GB of logs a month. Heavier traffic costs more."
                ),
                impact=Impact.MEDIUM,
            ),
            Assumption(
                statement=(
                    "You build the image from this Dockerfile in your own CI and push it to a "
                    "registry the task can pull from; CloudPilot deploys it by digest."
                ),
                impact=Impact.HIGH,
            ),
            Assumption(
                statement=(
                    "The application reads its database from DATABASE_URL, or from DB_HOST, "
                    "DB_PORT, DB_NAME, DB_USER and DB_PASSWORD, and creates its own tables."
                ),
                impact=Impact.HIGH,
            ),
            Assumption(
                statement=(
                    f"{health} answers 2xx when the service is healthy"
                    + ("" if service.health_endpoint else " (no health route was detected)")
                    + "."
                ),
                impact=Impact.HIGH if not service.health_endpoint else Impact.MEDIUM,
            ),
        ],
        security=SecurityDesign(
            network_isolation=(
                "Database in private subnets, reachable only from the task's security group; "
                "the task accepts traffic only from the load balancer; the load balancer accepts "
                "only the CIDR allowed at deploy time."
            ),
            encryption_at_rest=True,
            encryption_in_transit=False,
            secrets_strategy=(
                "Generated database password in AWS Secrets Manager, injected into the task as "
                "secrets; never stored by CloudPilot."
            ),
            least_privilege_notes=(
                "The task execution role may pull the image, write its log group and read only "
                "this deployment's secret."
            ),
            public_endpoints=["ALB HTTP :80 (allowed CIDR only)"],
        ),
        cost=CostEstimate(
            monthly_total=total,
            lines=lines,
            pricing_as_of=p.pricing_as_of,
            confidence=0.8,
        ),
        risks=[
            Finding(
                code="HTTP_ONLY",
                severity=Severity.WARNING,
                message="Traffic is plain HTTP on the load balancer's address; TLS needs a domain.",
                suggested_action="Add a domain and an ACM certificate before real users connect.",
            ),
            Finding(
                code="SINGLE_TASK",
                severity=Severity.WARNING,
                message="One task in one Availability Zone: a task restart means a short outage.",
                suggested_action="Run two tasks once the service matters.",
            ),
            Finding(
                code="NO_DB_BACKUPS",
                severity=Severity.WARNING,
                message=(
                    "Sandbox settings: no automated backups, no final snapshot, no deletion "
                    "protection; destroying the deployment deletes the data."
                ),
                suggested_action="Enable backups and deletion protection for real data.",
            ),
        ],
    )
