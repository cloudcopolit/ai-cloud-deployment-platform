"""AWS onboarding, plan -> hash-bound approval -> apply -> health -> destroy, and the failure
paths (ADR-027..033). AWS and OpenTofu are faked at the runner's tool boundary; the real-AWS
proof is scripts/real-flow.sh."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core import audit
from app.deploy import aws as deploy_aws
from app.deploy import runner
from app.deploy.aws import TempCredentials, Verification
from app.deploy.tofu import RunResult, TofuError
from app.deploy.verify import CleanCheck, HealthResult
from app.models import Approval, AuditLog, AWSAccount, Deployment
from tests.factories import (
    connected_repository,
    headers_for,
    make_user,
    run_queued_job_inline,
)
from tests.fakes import FakeGitHub

IMAGE = "333888905249.dkr.ecr.us-east-1.amazonaws.com/ref@sha256:" + "a" * 64
MY_IP = "203.0.113.7/32"


@pytest.fixture(autouse=True)
def deploy_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "architect_automated_archetypes", True)
    monkeypatch.setattr(settings, "cloudpilot_aws_access_key_id", "test-key-id")
    monkeypatch.setattr(settings, "cloudpilot_aws_secret_access_key", "test-secret")
    monkeypatch.setattr(
        "app.modules.deployments.service._platform_principal",
        lambda: "arn:aws:iam::333888905249:user/cloudpilot",
    )


def _verified(monkeypatch: pytest.MonkeyPatch, ok: bool = True) -> None:
    monkeypatch.setattr(
        deploy_aws,
        "verify_account",
        lambda **kw: Verification(
            ok,
            "arn:aws:sts::333888905249:assumed-role/CloudPilotDeployRole-x/cp-verify"
            if ok
            else None,
            True if ok else None,
            True if ok else None,
            "Verified." if ok else "AssumeRole with the External ID failed (AccessDenied).",
        ),
    )


def _world(
    client: TestClient, db: Session, fake: FakeGitHub, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    owner = make_user(db, "Owner")
    team, project, repo = connected_repository(db, fake, owner)
    h = headers_for(owner)
    analysis = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=h).json()["id"]
    assert run_queued_job_inline(db, fake, uuid.UUID(analysis)) == "SUCCESS"
    version = client.post(f"/analyses/{analysis}/architectures", json={}, headers=h)
    assert version.status_code == 201
    assert version.json()["architecture_data"]["automated"] is True
    account = client.post(
        f"/teams/{team.id}/aws-accounts", json={"aws_account_id": "333888905249"}, headers=h
    ).json()
    _verified(monkeypatch)
    assert (
        client.post(f"/aws-accounts/{account['id']}/verify", headers=h).json()["status"] == "ACTIVE"
    )
    return {
        "owner": owner,
        "team": team,
        "project": project,
        "h": h,
        "version": version.json(),
        "account": account,
    }


# ───────────────────────── fakes at the runner's tool boundary ─────────────────────────
def plan_json(deployment_id: str, *, open_ingress: bool = False) -> dict[str, Any]:
    tags = {"cloudpilot:deployment-id": deployment_id, "cloudpilot:managed-by": "cloudpilot"}

    def rc(address: str, type_: str, after: dict[str, Any]) -> dict[str, Any]:
        return {
            "address": address,
            "mode": "managed",
            "type": type_,
            "change": {"actions": ["create"], "after": after},
        }

    return {
        "terraform_version": "1.10.9",
        "variables": {"region": {"value": "us-east-1"}},
        "resource_changes": [
            rc("aws_vpc.this", "aws_vpc", {"tags_all": tags}),
            rc("aws_lb.this", "aws_lb", {"tags_all": tags, "subnets": ["a", "b"]}),
            rc(
                'aws_vpc_security_group_ingress_rule.alb_http["x"]',
                "aws_vpc_security_group_ingress_rule",
                {"cidr_ipv4": "0.0.0.0/0" if open_ingress else MY_IP},
            ),
            rc(
                "aws_ecs_task_definition.app",
                "aws_ecs_task_definition",
                {"tags_all": tags, "cpu": "256", "memory": "512"},
            ),
            rc("aws_ecs_service.app", "aws_ecs_service", {"tags_all": tags, "desired_count": 1}),
            rc(
                "aws_db_instance.this",
                "aws_db_instance",
                {"tags_all": tags, "instance_class": "db.t4g.micro", "allocated_storage": 20},
            ),
            rc("aws_secretsmanager_secret.db", "aws_secretsmanager_secret", {"tags_all": tags}),
            rc("aws_cloudwatch_log_group.app", "aws_cloudwatch_log_group", {"tags_all": tags}),
            rc("random_password.db", "random_password", {}),
        ],
    }


class FakeWorkspace:
    STORE: ClassVar[dict[str, bytes]] = {}
    fail_apply = False
    fail_destroy = False
    open_ingress = False

    def __init__(
        self,
        *,
        stack: str,
        deployment_id: str,
        region: str,
        state_bucket: str,
        variables: dict,
        creds: Any,
    ) -> None:
        import tempfile

        self.deployment_id = deployment_id
        self.workdir = Path(tempfile.mkdtemp())
        self.destroyed = False
        assert variables["image"].endswith("a" * 64)
        assert variables["ingress_cidrs"] == [MY_IP]
        assert state_bucket.startswith("cloudpilot-state-333888905249-")

    def plan_key(self, h: str) -> str:
        return f"deployments/{self.deployment_id}/plans/{h}.tfplan"

    def init(self) -> RunResult:
        return RunResult(0, ["Initializing the backend..."])

    def plan(self) -> tuple[Path, RunResult]:
        path = self.workdir / "plan.tfplan"
        path.write_bytes(f"plan for {self.deployment_id}".encode())
        return path, RunResult(0, ["Plan: 9 to add, 0 to change, 0 to destroy."])

    def show_json(self, plan: Path | None = None) -> dict[str, Any]:
        return plan_json(self.deployment_id, open_ingress=type(self).open_ingress)

    def apply(self, plan: Path) -> RunResult:
        if type(self).fail_apply:
            raise TofuError("apply", 1, ["Error: creating RDS DB Instance: quota exceeded"])
        return RunResult(0, ["Apply complete! Resources: 9 added, 0 changed, 0 destroyed."])

    def destroy(self) -> RunResult:
        if type(self).fail_destroy:
            raise TofuError("destroy", 1, ["Error: deleting VPC: DependencyViolation"])
        self.destroyed = True
        return RunResult(0, ["Destroy complete! Resources: 9 destroyed."])

    def outputs(self) -> dict[str, Any]:
        return {
            "health_url": "http://cp-x.elb.amazonaws.com/health",
            "endpoint_url": "http://cp-x.elb.amazonaws.com/",
            "cluster_name": "cp-x-cluster",
            "service_name": "cp-x-app",
            "task_family": "cp-x-app",
        }

    def state_resources(self) -> list[dict[str, str]]:
        if self.destroyed:
            return []
        return [
            {
                "address": "aws_vpc.this",
                "type": "aws_vpc",
                "id": "vpc-1",
                "arn": "arn:aws:ec2:::vpc/vpc-1",
            }
        ]

    def cleanup(self) -> None:
        pass


def tools(*, health_ok: bool = True, tamper: bool = False, clean: bool = True) -> runner.Tools:
    def s3_put(session: Any, bucket: str, key: str, path: Path) -> None:
        FakeWorkspace.STORE[key] = path.read_bytes()

    def s3_get(session: Any, bucket: str, key: str, path: Path) -> None:
        path.write_bytes(FakeWorkspace.STORE[key] + (b"tampered" if tamper else b""))

    return runner.Tools(
        assume=lambda role, **kw: TempCredentials(
            "AKIAEXAMPLE", "s", "t", datetime.now(UTC), kw["session_name"]
        ),
        workspace=FakeWorkspace,  # type: ignore[arg-type]
        session_for=lambda creds, region: object(),
        wait_for_service=lambda *a, **k: True,
        http_health=lambda url, **k: HealthResult(
            health_ok,
            url,
            3,
            200 if health_ok else 502,
            40,
            '{"status":"ok"}' if health_ok else "",
            None if health_ok else "HTTPStatus",
        ),
        verify_destroyed=lambda *a, **k: CleanCheck(
            clean, [] if clean else ["arn:aws:ec2:us-east-1:1:vpc/vpc-1"], [], 1, 1
        ),
        s3_put=s3_put,
        s3_get=s3_get,
    )


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeWorkspace.STORE.clear()
    FakeWorkspace.fail_apply = FakeWorkspace.fail_destroy = FakeWorkspace.open_ingress = False


def run_job(db: Session, expected_action: str, t: runner.Tools | None = None) -> str:
    claimed = runner.claim_next(db, "test-runner")
    assert claimed is not None
    deployment_id, action = claimed
    assert action == expected_action
    return runner.execute(db, deployment_id, action, t or tools())


def plan(client: TestClient, w: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    body = {
        "architecture_version_id": w["version"]["id"],
        "aws_account_id": w["account"]["id"],
        "image_uri": IMAGE,
        "ingress_cidrs": [MY_IP],
    } | overrides
    res = client.post(f"/projects/{w['project'].id}/deployments", json=body, headers=w["h"])
    assert res.status_code == 201, res.text
    return res.json()


# ───────────────────────── AWS accounts ─────────────────────────
def test_connecting_an_account_generates_names_and_a_long_unique_external_id(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user(db_session)
    team, *_ = connected_repository(db_session, fake_github, owner)
    a = client.post(
        f"/teams/{team.id}/aws-accounts",
        json={"aws_account_id": "333888905249"},
        headers=headers_for(owner),
    ).json()
    b = client.post(
        f"/teams/{team.id}/aws-accounts",
        json={"aws_account_id": "333888905249"},
        headers=headers_for(owner),
    ).json()
    assert a["status"] == "PENDING_VERIFICATION"
    assert len(a["external_id"]) >= 32
    assert a["external_id"] != b["external_id"]
    assert a["role_arn"].startswith(
        "arn:aws:iam::333888905249:role/cloudpilot/CloudPilotDeployRole-"
    )
    assert a["state_bucket"].startswith("cloudpilot-state-333888905249-")

    template = client.get(f"/aws-accounts/{a['id']}/onboarding", headers=headers_for(owner)).json()
    doc = json.loads(template["template"])
    trust = doc["Resources"]["DeployRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Principal"] == {"AWS": "arn:aws:iam::333888905249:user/cloudpilot"}
    assert trust["Condition"] == {"StringEquals": {"sts:ExternalId": a["external_id"]}}
    assert doc["Resources"]["DeployRole"]["Properties"]["PermissionsBoundary"] == {
        "Ref": "DeployBoundary"
    }
    bucket = doc["Resources"]["StateBucket"]["Properties"]
    assert bucket["VersioningConfiguration"] == {"Status": "Enabled"}
    assert bucket["PublicAccessBlockConfiguration"]["BlockPublicPolicy"] is True


def test_only_admins_connect_accounts_and_other_tenants_see_nothing(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, member, stranger = make_user(db_session), make_user(db_session), make_user(db_session)
    team, *_ = connected_repository(db_session, fake_github, owner)
    from app.models import TeamMember

    db_session.add(TeamMember(team_id=team.id, user_id=member.id, role="MEMBER"))
    db_session.flush()
    body = {"aws_account_id": "333888905249"}
    assert (
        client.post(
            f"/teams/{team.id}/aws-accounts", json=body, headers=headers_for(member)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/teams/{team.id}/aws-accounts", json=body, headers=headers_for(stranger)
        ).status_code
        == 404
    )
    account = client.post(
        f"/teams/{team.id}/aws-accounts", json=body, headers=headers_for(owner)
    ).json()
    assert (
        client.get(
            f"/aws-accounts/{account['id']}/onboarding", headers=headers_for(stranger)
        ).status_code
        == 404
    )


def test_verification_failure_is_recorded_honestly(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user(db_session)
    team, *_ = connected_repository(db_session, fake_github, owner)
    account = client.post(
        f"/teams/{team.id}/aws-accounts",
        json={"aws_account_id": "333888905249"},
        headers=headers_for(owner),
    ).json()
    _verified(monkeypatch, ok=False)
    res = client.post(f"/aws-accounts/{account['id']}/verify", headers=headers_for(owner)).json()
    assert res["status"] == "VERIFICATION_FAILED"
    assert "AccessDenied" in res["verification_message"]
    actions = db_session.scalars(select(AuditLog.action).where(AuditLog.team_id == team.id)).all()
    assert actions == ["AWS_ACCOUNT_CONNECTED", "AWS_ACCOUNT_VERIFICATION_FAILED"]


def test_without_cloudpilots_aws_identity_deployments_are_disabled(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    owner = make_user(db_session)
    team, *_ = connected_repository(db_session, fake_github, owner)
    account = client.post(
        f"/teams/{team.id}/aws-accounts",
        json={"aws_account_id": "333888905249"},
        headers=headers_for(owner),
    ).json()
    monkeypatch.setattr(settings, "cloudpilot_aws_access_key_id", None)
    res = client.post(f"/aws-accounts/{account['id']}/verify", headers=headers_for(owner))
    assert res.status_code == 503
    assert "No AWS call was made" in res.json()["error"]["message"]


# ───────────────────────── the happy path ─────────────────────────
def test_plan_approve_by_hash_apply_health_destroy(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    assert d["status"] == "QUEUED"
    assert [s["step_type"] for s in d["steps"]] == [
        "PLAN",
        "POLICY_CHECK",
        "APPROVAL",
        "APPLY",
        "HEALTH_CHECK",
        "DESTROY",
        "VERIFY_CLEAN",
    ]

    assert run_job(db_session, "plan") == "AWAITING_APPROVAL"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert len(d["plan_hash"]) == 64
    assert d["plan_summary"]["add"] == 9
    assert all(c["passed"] for c in d["policy_results"])
    assert d["cost_estimate"]["monthly_total"] > 0
    assert d["cost_estimate"]["pricing_as_of"].startswith("20")
    assert d["sessions"][0]["session_name"].startswith(f"cp-{uuid.UUID(d['id']).hex[:8]}-plan-")

    # apply before approval is refused, and a hash the reviewer did not see is refused
    assert client.post(f"/deployments/{d['id']}/apply", headers=w["h"]).status_code == 403
    wrong = client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": "0" * 64},
        headers=w["h"],
    )
    assert wrong.status_code == 409
    ok = client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    assert ok.status_code == 200
    assert ok.json()["plan_hash"] == d["plan_hash"]
    assert ok.json()["expires_at"] is not None

    assert (
        client.post(f"/deployments/{d['id']}/apply", headers=w["h"]).json()["status"]
        == "APPLY_QUEUED"
    )
    assert run_job(db_session, "apply") == "SUCCESS"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["health"]["passed"] is True
    assert d["live_endpoint"] == "http://cp-x.elb.amazonaws.com/"
    assert d["approval"]["status"] == "CONSUMED"
    assert d["resources"][0]["resource_type"] == "aws_vpc"

    # the approval was used up: a second apply is impossible
    assert client.post(f"/deployments/{d['id']}/apply", headers=w["h"]).status_code == 409

    assert (
        client.post(
            f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"]
        ).json()["status"]
        == "DESTROY_QUEUED"
    )
    assert run_job(db_session, "destroy") == "DESTROYED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["destroy_check"]["clean"] is True
    assert [s["session_name"].split("-")[2] for s in d["sessions"]] == ["plan", "apply", "destroy"]

    trail = [
        e["action"] for e in client.get(f"/deployments/{d['id']}/audit", headers=w["h"]).json()
    ]
    for expected in [
        "DEPLOYMENT_PLAN_REQUESTED",
        "PLAN_CREATED",
        "APPROVAL_REFUSED_HASH_MISMATCH",
        "DEPLOYMENT_APPROVED",
        "APPLY_REQUESTED",
        "APPLY_STARTED",
        "APPLY_SUCCEEDED",
        "HEALTH_CHECK_PASSED",
        "DESTROY_REQUESTED",
        "DESTROY_STARTED",
        "DESTROYED",
    ]:
        assert expected in trail
    assert audit.verify_chain(db_session, w["team"].id)


# ───────────────────────── refusals and failure paths ─────────────────────────
def test_members_cannot_plan_approve_apply_or_destroy(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models import TeamMember

    w = _world(client, db_session, fake_github, monkeypatch)
    member = make_user(db_session)
    db_session.add(TeamMember(team_id=w["team"].id, user_id=member.id, role="MEMBER"))
    db_session.flush()
    mh = headers_for(member)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=mh).json()  # members may look
    assert (
        client.post(
            f"/deployments/{d['id']}/approve",
            json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
            headers=mh,
        ).status_code
        == 403
    )
    assert client.post(f"/deployments/{d['id']}/apply", headers=mh).status_code == 403


def test_bad_inputs_are_rejected_before_anything_runs(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    url = f"/projects/{w['project'].id}/deployments"
    base = {"architecture_version_id": w["version"]["id"], "aws_account_id": w["account"]["id"]}
    tag_not_digest = base | {"image_uri": "nginx:latest", "ingress_cidrs": [MY_IP]}
    assert client.post(url, json=tag_not_digest, headers=w["h"]).status_code == 422
    world_open = base | {"image_uri": IMAGE, "ingress_cidrs": ["0.0.0.0/0"]}
    assert client.post(url, json=world_open, headers=w["h"]).status_code == 422


def test_unverified_account_and_non_automated_plans_cannot_be_planned(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    account = db_session.get(AWSAccount, uuid.UUID(w["account"]["id"]))
    assert account is not None
    account.status = "PENDING_VERIFICATION"
    db_session.flush()
    res = client.post(
        f"/projects/{w['project'].id}/deployments",
        json={
            "architecture_version_id": w["version"]["id"],
            "aws_account_id": w["account"]["id"],
            "image_uri": IMAGE,
            "ingress_cidrs": [MY_IP],
        },
        headers=w["h"],
    )
    assert res.status_code == 400
    assert "verify" in res.json()["error"]["message"]


def test_a_policy_violation_blocks_the_plan(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    FakeWorkspace.open_ingress = True
    d = plan(client, w)
    assert run_job(db_session, "plan") == "BLOCKED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    failed = [c["id"] for c in d["policy_results"] if not c["passed"]]
    assert failed == ["no_open_ingress"]
    res = client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    assert res.status_code == 409


def test_a_tampered_plan_file_is_never_applied(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    client.post(f"/deployments/{d['id']}/apply", headers=w["h"])
    assert run_job(db_session, "apply", tools(tamper=True)) == "FAILED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["error_code"] == "PLAN_HASH_MISMATCH"
    assert d["resources"] == []


def test_failed_apply_reports_what_exists_and_offers_destroy(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    client.post(f"/deployments/{d['id']}/apply", headers=w["h"])
    FakeWorkspace.fail_apply = True
    assert run_job(db_session, "apply") == "FAILED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["error_code"] == "APPLY_FAILED"
    assert "1 resource(s) exist" in d["error_message"]
    assert [r["status"] for r in d["resources"]] == ["FAILED"]
    apply_step = next(s for s in d["steps"] if s["step_type"] == "APPLY")
    assert "quota exceeded" in " ".join(apply_step["output_data"]["log_tail"])
    assert (
        client.post(
            f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"]
        ).status_code
        == 200
    )


def test_failed_health_check_keeps_the_infrastructure_and_says_so(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    client.post(f"/deployments/{d['id']}/apply", headers=w["h"])
    assert run_job(db_session, "apply", tools(health_ok=False)) == "FAILED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["error_code"] == "HEALTH_CHECK_FAILED"
    assert "still running" in d["error_message"]
    assert d["live_endpoint"] is None


def test_partial_destroy_is_reported_and_can_be_retried(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    client.post(f"/deployments/{d['id']}/apply", headers=w["h"])
    run_job(db_session, "apply")
    client.post(f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"])
    FakeWorkspace.fail_destroy = True
    assert run_job(db_session, "destroy") == "DESTROY_FAILED"
    FakeWorkspace.fail_destroy = False
    client.post(f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"])
    assert run_job(db_session, "destroy", tools(clean=False)) == "DESTROY_FAILED"  # leftovers found
    client.post(f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"])
    assert run_job(db_session, "destroy") == "DESTROYED"


def test_expired_approval_cannot_be_applied(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "APPROVED", "plan_hash": d["plan_hash"]},
        headers=w["h"],
    )
    approval = db_session.scalar(
        select(Approval).where(Approval.deployment_id == uuid.UUID(d["id"]))
    )
    assert approval is not None
    approval.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()
    res = client.post(f"/deployments/{d['id']}/apply", headers=w["h"])
    assert res.status_code == 409
    assert "expired" in res.json()["error"]["message"]


def test_rejection_cancels_and_skips_the_rest(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    run_job(db_session, "plan")
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    res = client.post(
        f"/deployments/{d['id']}/approve",
        json={"decision": "REJECTED", "plan_hash": d["plan_hash"], "reason": "too expensive"},
        headers=w["h"],
    )
    assert res.json()["status"] == "REJECTED"
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert d["status"] == "CANCELLED"
    assert {s["status"] for s in d["steps"] if s["step_type"] in ("APPLY", "HEALTH_CHECK")} == {
        "SKIPPED"
    }


def test_a_lost_runner_ends_timed_out_not_running(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    d = plan(client, w)
    claimed = runner.claim_next(db_session, "ghost")
    assert claimed is not None
    row = db_session.get(Deployment, uuid.UUID(d["id"]))
    assert row is not None
    row.status = "APPLYING"
    row.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.flush()
    assert runner.sweep(db_session) == 1
    d = client.get(f"/deployments/{d['id']}", headers=w["h"]).json()
    assert (d["status"], d["error_code"]) == ("TIMED_OUT", "RUNNER_LOST")
    assert (
        client.post(
            f"/deployments/{d['id']}/destroy", json={"confirm": "destroy"}, headers=w["h"]
        ).status_code
        == 200
    )


def test_audit_log_is_append_only(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = _world(client, db_session, fake_github, monkeypatch)
    entry = db_session.scalar(select(AuditLog).where(AuditLog.team_id == w["team"].id).limit(1))
    assert entry is not None
    for statement in (
        "UPDATE audit_logs SET action = 'X' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ):
        nested = db_session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            db_session.execute(text(statement), {"id": entry.id})
        nested.rollback()
    assert audit.verify_chain(db_session, w["team"].id)
