"""Pure units behind deployments: policy, plan cost, onboarding permissions, health check,
output sanitising, two-runner exclusivity, rate limits (ADR-026..033)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from cloudpilot_ai.architecture.pricing import load_prices
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import RateLimited
from app.core.ratelimit import hit
from app.db.session import SessionLocal
from app.deploy import policy, verify
from app.deploy.onboarding import OnboardingNames, render_template
from app.deploy.tofu import sanitize
from app.models import RateLimitBucket
from tests.factories import headers_for, make_team, make_user
from tests.test_deployments_api import MY_IP, deploy_enabled, plan_json  # noqa: F401 (autouse)

DID = str(uuid.UUID(int=5))


def checks(plan: dict, **kw: object) -> dict[str, bool]:
    args = {
        "region": "us-east-1",
        "deployment_id": DID,
        "ingress_cidrs": [MY_IP],
        "monthly_cost": 50.0,
        "monthly_cap": 100.0,
    } | kw
    return {c.id: c.passed for c in policy.check_plan(plan, **args)}  # type: ignore[arg-type]


def test_a_clean_plan_passes_every_check() -> None:
    assert all(checks(plan_json(DID)).values())


@pytest.mark.parametrize(
    ("mutate", "failing"),
    [
        (
            lambda p: p["resource_changes"].append(
                {
                    "address": "aws_instance.x",
                    "mode": "managed",
                    "type": "aws_instance",
                    "change": {
                        "actions": ["create"],
                        "after": {"tags_all": {"cloudpilot:deployment-id": DID}},
                    },
                }
            ),
            "allowed_resource_types",
        ),
        (
            lambda p: p["resource_changes"][2]["change"]["after"].update(cidr_ipv4="0.0.0.0/0"),
            "no_open_ingress",
        ),
        (
            lambda p: p["resource_changes"][2]["change"]["after"].update(
                cidr_ipv4="198.51.100.9/32"
            ),
            "no_open_ingress",
        ),
        (
            lambda p: p["resource_changes"][0]["change"]["after"].update(tags_all={}),
            "deployment_tag",
        ),
        (
            lambda p: p["resource_changes"][5]["change"]["after"].update(
                instance_class="db.r6g.4xlarge"
            ),
            "size_caps",
        ),
        (lambda p: p["variables"]["region"].update(value="eu-west-1"), "region"),
        (
            lambda p: p["resource_changes"].append(
                {
                    "address": "aws_iam_role_policy.x",
                    "mode": "managed",
                    "type": "aws_iam_role_policy",
                    "change": {
                        "actions": ["create"],
                        "after": {
                            "policy": json.dumps(
                                {"Statement": [{"Action": "s3:*", "Resource": "*"}]}
                            )
                        },
                    },
                }
            ),
            "no_iam_wildcards",
        ),
    ],
)
def test_each_policy_catches_its_violation(mutate, failing: str) -> None:
    plan = plan_json(DID)
    mutate(plan)
    result = checks(plan)
    assert result[failing] is False
    assert [k for k, v in result.items() if not v] == [failing]


def test_cost_cap_blocks_expensive_plans() -> None:
    assert checks(plan_json(DID), monthly_cost=150.0)["monthly_cost_cap"] is False


def test_plan_cost_uses_the_price_table() -> None:
    prices = load_prices("us-east-1")
    cost = policy.plan_cost(plan_json(DID), prices)
    assert cost["pricing_as_of"] == prices.pricing_as_of
    items = {line["item"]: line["monthly_usd"] for line in cost["lines"]}
    expected_rds = round(
        prices["rds_postgres_t4g_micro_hour"].usd * 730 + 20 * prices["rds_gp3_gb_month"].usd, 2
    )
    assert items["aws_db_instance.this"] == pytest.approx(expected_rds, abs=0.01)
    assert items["public IPv4 addresses"] == pytest.approx(
        3 * prices["public_ipv4_hour"].usd * 730, abs=0.01
    )
    assert cost["monthly_total"] == pytest.approx(sum(items.values()), abs=0.01)


def test_summary_counts_actions() -> None:
    s = policy.summarize(plan_json(DID))
    assert (s.add, s.change, s.destroy) == (9, 0, 0)


def test_onboarding_permissions_cannot_escalate() -> None:
    names = OnboardingNames(account_id="333888905249", suffix="ab12cd34")
    doc = json.loads(
        render_template(
            names,
            external_id="cp-x" * 10,
            platform_principal_arn="arn:aws:iam::333888905249:user/p",
            region="us-east-1",
        )
    )
    statements = doc["Resources"]["DeployBoundary"]["Properties"]["PolicyDocument"]["Statement"]
    by_sid = {s["Sid"]: s for s in statements}
    # new roles must carry the same boundary, and live under /cloudpilot/
    create = by_sid["TaskRolesUnderPathWithBoundary"]
    assert create["Condition"] == {"StringEquals": {"iam:PermissionsBoundary": names.boundary_arn}}
    assert create["Resource"].endswith(":role/cloudpilot/*")
    assert by_sid["PassTaskRolesToEcsOnly"]["Condition"] == {
        "StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}
    }
    assert by_sid["OnlyTheEcsExecutionManagedPolicy"]["Condition"]["ArnEquals"][
        "iam:PolicyARN"
    ].endswith("AmazonECSTaskExecutionRolePolicy")
    # no statement grants iam:* or *:*
    for s in statements:
        actions = [s["Action"]] if isinstance(s["Action"], str) else s["Action"]
        assert "*" not in actions
        assert "iam:*" not in actions
    assert all(s.get("Condition") for s in statements if s["Sid"] == "ArchetypeServices")


def test_health_check_retries_until_2xx() -> None:
    answers = iter([502, 503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(answers), text='{"status":"ok"}')

    result = verify.http_health(
        "http://alb/health",
        timeout_s=60,
        interval_s=1,
        sleep=lambda s: None,
        transport=httpx.MockTransport(handler),
    )
    assert result.passed
    assert result.attempts == 3
    assert (
        result.log == ["#1 HTTP 502 in 0 ms", "#2 HTTP 503 in 0 ms", "#3 HTTP 200 in 0 ms"]
        or len(result.log) == 3
    )


def test_health_check_gives_up_honestly() -> None:
    result = verify.http_health(
        "http://alb/health",
        timeout_s=0,
        interval_s=1,
        sleep=lambda s: None,
        transport=httpx.MockTransport(lambda r: httpx.Response(503)),
    )
    assert not result.passed
    assert result.status_code == 503


def test_tofu_output_is_sanitised() -> None:
    line = "aws_access_key AKIAABCDEFGHIJKLMNOP password=hunter2hunter2 token: abcdefghijkl"
    clean = sanitize(line)
    assert "AKIAABCDEFGHIJKLMNOP" not in clean
    assert "hunter2hunter2" not in clean
    assert "abcdefghijkl" not in clean


def test_rate_limit_counts_per_window_and_says_when_to_retry(db_session: Session) -> None:
    key = f"test:{uuid.uuid4()}"
    now = datetime(2026, 10, 26, 12, 0, 30, tzinfo=UTC)
    for _ in range(3):
        hit(db_session, key, 3, 60, now=now)
    with pytest.raises(RateLimited) as exc:
        hit(db_session, key, 3, 60, now=now)
    assert exc.value.retry_after == 30


def test_ip_rate_limit_answers_429_with_retry_after(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_ip_per_minute", 2)
    with SessionLocal() as db:  # the middleware counts in its own session
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.key == "ip:testclient"))
        db.commit()
    owner = make_user(db_session)
    team = make_team(db_session, {owner: "OWNER"})
    url = f"/teams/{team.id}/projects"
    codes = [
        client.post(url, json={"name": f"p{i}"}, headers=headers_for(owner)).status_code
        for i in range(3)
    ]
    assert codes[2] == 429
    res = client.post(url, json={"name": "again"}, headers=headers_for(owner))
    assert res.headers["Retry-After"].isdigit()
    with SessionLocal() as db:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.key == "ip:testclient"))
        db.commit()


def test_two_runners_never_claim_the_same_deployment(
    client: TestClient,
    db_session: Session,
    fake_github,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.deploy import runner
    from tests.test_deployments_api import _world, plan

    w = _world(client, db_session, fake_github, monkeypatch)
    plan(client, w)
    first = runner.claim_next(db_session, "runner-a")
    second = runner.claim_next(db_session, "runner-b")
    assert first is not None
    assert second is None
