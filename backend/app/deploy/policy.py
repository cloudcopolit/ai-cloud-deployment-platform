"""Plan policy checks and cost, in plain code over `tofu show -json` (ADR-033).

A plan that breaks a rule is BLOCKED: it cannot be approved or applied.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from cloudpilot_ai.architecture.pricing import HOURS_PER_MONTH, PriceTable

# The only resource types the container-postgres stack may create.
ALLOWED_TYPES = frozenset(
    {
        "aws_vpc",
        "aws_internet_gateway",
        "aws_subnet",
        "aws_route_table",
        "aws_route",
        "aws_route_table_association",
        "aws_security_group",
        "aws_vpc_security_group_ingress_rule",
        "aws_vpc_security_group_egress_rule",
        "aws_lb",
        "aws_lb_target_group",
        "aws_lb_listener",
        "aws_db_subnet_group",
        "aws_db_instance",
        "aws_secretsmanager_secret",
        "aws_secretsmanager_secret_version",
        "aws_cloudwatch_log_group",
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_ecs_cluster",
        "aws_ecs_task_definition",
        "aws_ecs_service",
        "random_password",
    }
)
UNTAGGABLE = frozenset(
    {
        "aws_route",
        "aws_route_table_association",
        "aws_lb_listener",  # tagged, but tags are optional in older ELB APIs
        "aws_secretsmanager_secret_version",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "random_password",
        "aws_vpc_security_group_egress_rule",
        "aws_vpc_security_group_ingress_rule",
    }
)
MAX_TASK_CPU = 1024
MAX_TASK_MEMORY = 2048
ALLOWED_DB_CLASSES = frozenset({"db.t4g.micro", "db.t4g.small"})


@dataclass(frozen=True)
class Check:
    id: str
    passed: bool
    message: str


@dataclass(frozen=True)
class PlanSummary:
    add: int
    change: int
    destroy: int
    resources: list[dict[str, str]]  # address, type, action


def _changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [rc for rc in plan.get("resource_changes", []) if rc.get("mode") == "managed"]


def _after(rc: dict[str, Any]) -> dict[str, Any]:
    return (rc.get("change") or {}).get("after") or {}


def summarize(plan: dict[str, Any]) -> PlanSummary:
    counts: Counter[str] = Counter()
    rows = []
    for rc in _changes(plan):
        actions = rc["change"]["actions"]
        action = (
            "replace" if actions in (["delete", "create"], ["create", "delete"]) else actions[0]
        )
        if action == "no-op" or action == "read":
            continue
        counts["add" if action == "create" else "destroy" if action == "delete" else "change"] += 1
        if action == "replace":
            counts["add"] += 1
        rows.append({"address": rc["address"], "type": rc["type"], "action": action})
    return PlanSummary(counts["add"], counts["change"], counts["destroy"], rows)


def check_plan(
    plan: dict[str, Any],
    *,
    region: str,
    deployment_id: str,
    ingress_cidrs: list[str],
    monthly_cost: float,
    monthly_cap: float,
) -> list[Check]:
    changes = [rc for rc in _changes(plan) if rc["change"]["actions"] != ["no-op"]]
    checks: list[Check] = []

    unknown = sorted({rc["type"] for rc in changes} - ALLOWED_TYPES)
    checks.append(
        Check(
            "allowed_resource_types",
            not unknown,
            "Only the archetype's resource types."
            if not unknown
            else f"Not allowed: {', '.join(unknown)}",
        )
    )

    open_ingress = []
    for rc in changes:
        after = _after(rc)
        if rc["type"] == "aws_vpc_security_group_ingress_rule":
            cidr = after.get("cidr_ipv4")
            if cidr == "0.0.0.0/0" or (cidr and cidr not in ingress_cidrs):
                open_ingress.append(f"{rc['address']} ({cidr})")
        if rc["type"] == "aws_security_group":
            for rule in after.get("ingress") or []:
                if "0.0.0.0/0" in (rule.get("cidr_blocks") or []):
                    open_ingress.append(rc["address"])
    checks.append(
        Check(
            "no_open_ingress",
            not open_ingress,
            "Ingress only from the allowed CIDRs and between our own security groups."
            if not open_ingress
            else f"Ingress wider than allowed: {', '.join(open_ingress)}",
        )
    )

    wildcard = []
    for rc in changes:
        if rc["type"] != "aws_iam_role_policy":
            continue
        doc = _after(rc).get("policy")
        statements = json.loads(doc).get("Statement", []) if isinstance(doc, str) else []
        for st in statements if isinstance(statements, list) else [statements]:
            actions = st.get("Action")
            actions = [actions] if isinstance(actions, str) else actions or []
            if any(a == "*" or a.endswith(":*") for a in actions) or st.get("Resource") == "*":
                wildcard.append(rc["address"])
    checks.append(
        Check(
            "no_iam_wildcards",
            not wildcard,
            "IAM policies name exact actions and resources."
            if not wildcard
            else f"Wildcards in {', '.join(wildcard)}",
        )
    )

    untagged = []
    for rc in changes:
        if rc["type"] in UNTAGGABLE or rc["change"]["actions"] == ["delete"]:
            continue
        tags = _after(rc).get("tags_all") or {}
        if isinstance(tags, dict) and tags.get("cloudpilot:deployment-id") != deployment_id:
            untagged.append(rc["address"])
    checks.append(
        Check(
            "deployment_tag",
            not untagged,
            "Every taggable resource carries cloudpilot:deployment-id."
            if not untagged
            else f"Missing the deployment tag: {', '.join(untagged[:6])}",
        )
    )

    region_ok = (plan.get("variables", {}).get("region") or {}).get("value") == region
    checks.append(Check("region", region_ok, f"Everything is created in {region}."))

    too_big = []
    for rc in changes:
        after = _after(rc)
        if rc["type"] == "aws_ecs_task_definition" and (
            int(after.get("cpu") or 0) > MAX_TASK_CPU
            or int(after.get("memory") or 0) > MAX_TASK_MEMORY
        ):
            too_big.append(rc["address"])
        if (
            rc["type"] == "aws_db_instance"
            and after.get("instance_class") not in ALLOWED_DB_CLASSES
        ):
            too_big.append(rc["address"])
        if rc["type"] == "aws_ecs_service" and int(after.get("desired_count") or 0) > 2:
            too_big.append(rc["address"])
    checks.append(
        Check(
            "size_caps",
            not too_big,
            "Sizes within the sandbox caps."
            if not too_big
            else f"Over the caps: {', '.join(too_big)}",
        )
    )

    checks.append(
        Check(
            "monthly_cost_cap",
            monthly_cost <= monthly_cap,
            f"Estimated ${monthly_cost:.2f}/month (cap ${monthly_cap:.2f}).",
        )
    )
    return checks


def plan_cost(plan: dict[str, Any], prices: PriceTable) -> dict[str, Any]:
    """Monthly cost of what the plan creates, from the same price table as the architecture."""
    lines: list[dict[str, Any]] = []

    def add(item: str, usd: float, basis: str) -> None:
        lines.append({"item": item, "monthly_usd": round(usd, 2), "basis": basis})

    p = prices
    public_ips = 0
    for rc in _changes(plan):
        if "create" not in rc["change"]["actions"]:
            continue
        after = _after(rc)
        if rc["type"] == "aws_ecs_service":
            count = int(after.get("desired_count") or 1)
            public_ips += count
            task = next(
                (_after(t) for t in _changes(plan) if t["type"] == "aws_ecs_task_definition"), {}
            )
            vcpu = int(task.get("cpu") or 256) / 1024 * count
            gb = int(task.get("memory") or 512) / 1024 * count
            add(
                rc["address"],
                (p["fargate_vcpu_hour"].usd * vcpu + p["fargate_gb_hour"].usd * gb)
                * HOURS_PER_MONTH,
                f"{count} Fargate task(s): {vcpu:g} vCPU + {gb:g} GB, 730 h",
            )
        elif rc["type"] == "aws_lb":
            public_ips += len(after.get("subnets") or []) or 2
            add(
                rc["address"],
                (p["alb_hour"].usd + 0.5 * p["alb_lcu_hour"].usd) * HOURS_PER_MONTH,
                "ALB hours + 0.5 LCU average, 730 h",
            )
        elif rc["type"] == "aws_db_instance":
            klass = after.get("instance_class")
            hourly = p["rds_postgres_t4g_micro_hour"].usd if klass == "db.t4g.micro" else None
            storage = int(after.get("allocated_storage") or 20)
            if hourly is None:
                add(rc["address"], 0.0, f"{klass}: not in the price table (not priced)")
            else:
                add(
                    rc["address"],
                    hourly * HOURS_PER_MONTH + storage * p["rds_gp3_gb_month"].usd,
                    f"{klass} Single-AZ, 730 h + {storage} GB gp3",
                )
        elif rc["type"] == "aws_secretsmanager_secret":
            add(rc["address"], p["secretsmanager_secret_month"].usd, "1 secret")
        elif rc["type"] == "aws_cloudwatch_log_group":
            add(
                rc["address"],
                p["cloudwatch_logs_ingest_gb"].usd + p["cloudwatch_logs_storage_gb_month"].usd,
                "1 GB ingested + 1 GB stored (assumption)",
            )
    if public_ips:
        add(
            "public IPv4 addresses",
            public_ips * p["public_ipv4_hour"].usd * HOURS_PER_MONTH,
            f"{public_ips} in-use public IPv4 x ${p['public_ipv4_hour'].usd}/h, 730 h",
        )
    return {
        "currency": "USD",
        "monthly_total": round(sum(line["monthly_usd"] for line in lines), 2),
        "lines": lines,
        "pricing_as_of": p.pricing_as_of,
        "source": p.source,
        "delta_note": "First deployment: the whole stack is new, so the delta is the full cost.",
    }


def checks_json(checks: list[Check]) -> list[dict[str, Any]]:
    return [asdict(c) for c in checks]
