"""After apply: wait for ECS and check real HTTP health. After destroy: prove nothing tagged
with the deployment id is left (ADR-032)."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError, WaiterError

from app.deploy.aws import client

TAG_KEY = "cloudpilot:deployment-id"


@dataclass
class HealthResult:
    passed: bool
    url: str
    attempts: int
    status_code: int | None = None
    latency_ms: int | None = None
    body_excerpt: str | None = None
    error: str | None = None
    ecs_stable: bool | None = None
    log: list[str] = field(default_factory=list)

    def json(self) -> dict[str, Any]:
        return asdict(self)


def wait_for_service(
    session: boto3.session.Session, cluster: str, service: str, timeout_s: int
) -> bool:
    waiter = client(session, "ecs").get_waiter("services_stable")
    try:
        waiter.wait(
            cluster=cluster,
            services=[service],
            WaiterConfig={"Delay": 15, "MaxAttempts": max(1, timeout_s // 15)},
        )
        return True
    except WaiterError:
        return False


def http_health(
    url: str,
    *,
    timeout_s: int = 600,
    interval_s: float = 10,
    sleep: Callable[[float], None] = time.sleep,
    transport: httpx.BaseTransport | None = None,
) -> HealthResult:
    """GET the health URL until it answers 2xx or time runs out. The ALB needs a few minutes
    to register the task, so early 502/503s are expected and retried."""
    result = HealthResult(passed=False, url=url, attempts=0)
    deadline = time.monotonic() + timeout_s
    with httpx.Client(timeout=10, follow_redirects=False, transport=transport) as http:
        while True:
            result.attempts += 1
            started = time.monotonic()
            try:
                response = http.get(url)
                result.status_code = response.status_code
                result.latency_ms = int((time.monotonic() - started) * 1000)
                result.body_excerpt = response.text[:300]
                result.error = None
                result.log.append(
                    f"#{result.attempts} HTTP {response.status_code} in {result.latency_ms} ms"
                )
                if 200 <= response.status_code < 300:
                    result.passed = True
                    return result
            except httpx.HTTPError as exc:
                result.error = type(exc).__name__
                result.log.append(f"#{result.attempts} {type(exc).__name__}")
            if time.monotonic() + interval_s > deadline:
                result.log = result.log[-20:]
                return result
            sleep(interval_s)


@dataclass
class CleanCheck:
    clean: bool
    remaining: list[str]  # still exist, confirmed with the owning service
    indexed_but_gone: list[str]  # listed by the tagging index, but deleted / stopped
    deleted_task_definitions: int
    attempts: int

    def json(self) -> dict[str, Any]:
        return asdict(self)


def _live(arn: str, session: boto3.session.Session) -> bool:
    """The tagging index lags; ask the owning service whether a listed ARN still exists."""
    try:
        if ":ecs:" in arn and ":task/" in arn:
            cluster = arn.split(":task/")[1].split("/")[0]
            tasks = client(session, "ecs").describe_tasks(cluster=cluster, tasks=[arn])["tasks"]
            return any(t.get("lastStatus") != "STOPPED" for t in tasks)
        if ":ecs:" in arn and ":task-definition/" in arn:
            defs = client(session, "ecs").describe_task_definition(taskDefinition=arn)
            return defs["taskDefinition"].get("status") not in {"DELETE_IN_PROGRESS"}
        if ":secretsmanager:" in arn:
            try:
                info = client(session, "secretsmanager").describe_secret(SecretId=arn)
            except ClientError:
                return False
            return "DeletedDate" not in info
        if ":rds:" in arn and ":db:" in arn:
            name = arn.split(":db:")[1]
            try:
                client(session, "rds").describe_db_instances(DBInstanceIdentifier=name)
            except ClientError:
                return False
            return True
        if ":logs:" in arn:
            name = arn.split(":log-group:")[1].rstrip(":*")
            groups = client(session, "logs").describe_log_groups(logGroupNamePrefix=name)[
                "logGroups"
            ]
            return any(g["logGroupName"] == name for g in groups)
    except ClientError:
        return False
    return True  # anything else: trust the index


def delete_inactive_task_definitions(session: boto3.session.Session, family: str | None) -> int:
    """ECS keeps deregistered revisions (INACTIVE, still tagged) until they are deleted."""
    if not family:
        return 0
    ecs = client(session, "ecs")
    arns = ecs.list_task_definitions(familyPrefix=family, status="INACTIVE").get(
        "taskDefinitionArns", []
    )
    arns += ecs.list_task_definitions(familyPrefix=family, status="ACTIVE").get(
        "taskDefinitionArns", []
    )
    for i in range(0, len(arns), 10):
        batch = arns[i : i + 10]
        for arn in batch:
            with contextlib.suppress(ClientError):  # already INACTIVE
                ecs.deregister_task_definition(taskDefinition=arn)
        ecs.delete_task_definitions(taskDefinitions=batch)
    return len(arns)


def tagged_resources(session: boto3.session.Session, deployment_id: str) -> list[str]:
    tagging = client(session, "resourcegroupstaggingapi")
    arns: list[str] = []
    token = ""
    while True:
        page = tagging.get_resources(
            TagFilters=[{"Key": TAG_KEY, "Values": [deployment_id]}],
            ResourcesPerPage=100,
            **({"PaginationToken": token} if token else {}),
        )
        arns += [r["ResourceARN"] for r in page.get("ResourceTagMappingList", [])]
        token = page.get("PaginationToken") or ""
        if not token:
            return arns


def verify_destroyed(
    session: boto3.session.Session,
    deployment_id: str,
    *,
    task_family: str | None,
    timeout_s: int = 600,
    interval_s: float = 20,
    sleep: Callable[[float], None] = time.sleep,
) -> CleanCheck:
    deleted = delete_inactive_task_definitions(session, task_family)
    deadline = time.monotonic() + timeout_s
    attempts = 0
    while True:
        attempts += 1
        indexed = tagged_resources(session, deployment_id)
        remaining = [arn for arn in indexed if _live(arn, session)]
        if not remaining or time.monotonic() + interval_s > deadline:
            gone = [arn for arn in indexed if arn not in remaining]
            return CleanCheck(not remaining, remaining, gone, deleted, attempts)
        sleep(interval_s)
