"""The adapters at the edge of deployments, without AWS: the OpenTofu workspace (against a fake
`tofu` executable), STS verification, ECS/HTTP/tagging checks, and the runner loop."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
import threading
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError, WaiterError
from sqlalchemy.orm import Session

from app.deploy import aws, runner, verify
from app.deploy import tofu as tofu_mod
from app.deploy.aws import TempCredentials

CREDS = TempCredentials(
    "ASIAFAKEFAKEFAKEFAKE", "secret-part", "token-part", datetime.now(UTC), "cp-x-plan-1"
)

FAKE_TOFU = r'''#!{python}
"""Records its argv and environment, and answers like tofu would."""
import json, os, sys
log = os.path.join(os.getcwd(), "calls.jsonl")
with open(log, "a") as fh:
    fh.write(json.dumps({{"argv": sys.argv[1:], "env": sorted(os.environ)}}) + "\n")
cmd = sys.argv[1]
if cmd == "plan":
    out = [a for a in sys.argv if a.startswith("-out=")][0][5:]
    open(out, "wb").write(b"PLANBYTES")
    print("Plan: 3 to add, 0 to change, 0 to destroy. AKIAABCDEFGHIJKLMNOP")
elif cmd == "show":
    if len(sys.argv) > 3:
        print(json.dumps({{"resource_changes": []}}))
    else:
        vpc = {{"mode": "managed", "address": "aws_vpc.this", "type": "aws_vpc",
               "values": {{"id": "vpc-1", "arn": "arn:vpc"}}}}
        data = {{"mode": "data", "address": "data.x", "type": "aws_x", "values": {{}}}}
        bucket = {{"mode": "managed", "address": "module.m.aws_s3_bucket.b",
                  "type": "aws_s3_bucket", "values": {{"id": "b"}}}}
        root = {{"resources": [vpc, data], "child_modules": [{{"resources": [bucket]}}]}}
        print(json.dumps({{"values": {{"root_module": root}}}}))
elif cmd == "output":
    outputs = {{"health_url": {{"value": "http://x/health", "sensitive": False}},
               "pw": {{"value": "s", "sensitive": True}}}}
    print(json.dumps(outputs))
elif cmd == "apply" and os.environ.get("FAIL_APPLY"):
    print("Error: boom password=hunter2hunter2", file=sys.stderr)
    sys.exit(1)
else:
    print(cmd + " ok")
'''


@pytest.fixture
def fake_tofu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stacks = tmp_path / "stacks" / "container-postgres"
    stacks.mkdir(parents=True)
    (stacks / "main.tf").write_text("# stack\n")
    exe = tmp_path / "tofu"
    exe.write_text(FAKE_TOFU.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(tofu_mod, "STACKS_DIR", tmp_path / "stacks")
    monkeypatch.setattr(tofu_mod, "TOFU", str(exe))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("CLOUDPILOT_AWS_SECRET_ACCESS_KEY", "must-never-reach-tofu")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localstack:4566")
    monkeypatch.setenv("HTTPS_PROXY", "http://egress-proxy:3128")
    return tmp_path


def workspace() -> tofu_mod.Workspace:
    return tofu_mod.Workspace(
        stack="container-postgres",
        deployment_id="d-1",
        region="us-east-1",
        state_bucket="cloudpilot-state-1-ab",
        variables={"image": "x"},
        creds=CREDS,
    )


def test_workspace_runs_tofu_with_a_minimal_environment(fake_tofu: Path) -> None:
    ws = workspace()
    assert json.loads((ws.workdir / "cloudpilot.auto.tfvars.json").read_text()) == {"image": "x"}
    ws.init()
    path, result = ws.plan()
    assert path.read_bytes() == b"PLANBYTES"
    assert "AKIAABCDEFGHIJKLMNOP" not in " ".join(result.tail)  # masked
    assert tofu_mod.file_sha256(path) == hashlib.sha256(b"PLANBYTES").hexdigest()
    assert ws.show_json(path) == {"resource_changes": []}
    assert ws.outputs() == {"health_url": "http://x/health"}  # sensitive outputs dropped
    assert [r["address"] for r in ws.state_resources()] == [
        "aws_vpc.this",
        "module.m.aws_s3_bucket.b",
    ]
    ws.destroy()
    calls = [json.loads(line) for line in (ws.workdir / "calls.jsonl").read_text().splitlines()]
    init = calls[0]["argv"]
    assert "-backend-config=bucket=cloudpilot-state-1-ab" in init
    assert "-backend-config=key=deployments/d-1/terraform.tfstate" in init
    assert "-backend-config=use_lockfile=true" in init
    env = set(calls[0]["env"])
    assert {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "HTTPS_PROXY"} <= env
    assert "CLOUDPILOT_AWS_SECRET_ACCESS_KEY" not in env  # CloudPilot's own key never reaches tofu
    assert "AWS_ENDPOINT_URL" not in env  # nor the LocalStack endpoint
    assert ws.plan_key("abc") == "deployments/d-1/plans/abc.tfplan"
    ws.cleanup()
    assert not ws.workdir.exists()


def test_failed_tofu_command_raises_with_a_sanitised_tail(
    fake_tofu: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAIL_APPLY", "1")
    monkeypatch.setattr(tofu_mod, "PASSTHROUGH", (*tofu_mod.PASSTHROUGH, "FAIL_APPLY"))
    ws = workspace()
    with pytest.raises(tofu_mod.TofuError) as exc:
        ws.apply(ws.workdir / "p")
    assert exc.value.step == "apply"
    assert "hunter2hunter2" not in " ".join(exc.value.tail)
    assert repr(CREDS).count("secret-part") == 0


# ───────────────────────── STS verification ─────────────────────────
def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "AssumeRole")


class FakeClient:
    def __init__(self, account: str = "333888905249", bucket_ok: bool = True) -> None:
        self.account = account
        self.bucket_ok = bucket_ok

    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": self.account, "Arn": f"arn:aws:sts::{self.account}:assumed-role/R/s"}

    def head_bucket(self, Bucket: str) -> None:
        if not self.bucket_ok:
            raise _client_error("404")


@pytest.mark.parametrize(
    ("enforced", "account", "bucket_ok", "ok", "message"),
    [
        (True, "333888905249", True, True, "Verified."),
        (False, "333888905249", True, False, "WITHOUT the External ID"),
        (True, "999999999999", True, False, "belongs to account 999999999999"),
        (True, "333888905249", False, False, "not reachable"),
    ],
)
def test_verify_account_checks_identity_external_id_and_bucket(
    monkeypatch: pytest.MonkeyPatch,
    enforced: bool,
    account: str,
    bucket_ok: bool,
    ok: bool,
    message: str,
) -> None:
    def assume(
        role: str, *, external_id: str | None, session_name: str, duration_s: int = 3600
    ) -> TempCredentials:
        if external_id is None and enforced:
            raise _client_error("AccessDenied")
        return CREDS

    monkeypatch.setattr(aws, "assume", assume)
    monkeypatch.setattr(aws, "session_for", lambda creds, region: object())
    monkeypatch.setattr(
        aws, "client", lambda session, service, region=None: FakeClient(account, bucket_ok)
    )
    result = aws.verify_account(
        account_id="333888905249",
        role_arn="arn:r",
        external_id="cp-x",
        state_bucket="b",
        region="us-east-1",
        session_name="s",
    )
    assert result.ok is ok
    assert message in result.message


def test_verify_account_reports_a_failed_assume_role(monkeypatch: pytest.MonkeyPatch) -> None:
    def assume(*a: Any, **k: Any) -> TempCredentials:
        raise _client_error("AccessDenied")

    monkeypatch.setattr(aws, "assume", assume)
    result = aws.verify_account(
        account_id="1",
        role_arn="r",
        external_id="x",
        state_bucket="b",
        region="us-east-1",
        session_name="s",
    )
    assert not result.ok
    assert "AccessDenied" in result.message


def test_platform_identity_comes_only_from_cloudpilot_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "cloudpilot_aws_access_key_id", None)
    assert not aws.deploy_enabled()
    with pytest.raises(aws.DeployUnavailable):
        aws.platform_session()
    monkeypatch.setattr(settings, "cloudpilot_aws_access_key_id", "AKIAEXAMPLE")
    monkeypatch.setattr(settings, "cloudpilot_aws_secret_access_key", "x")
    session = aws.platform_session()
    sts = aws.client(session, "sts")
    # the containers' AWS_ENDPOINT_URL (LocalStack) is ignored for CloudPilot's own identity
    assert sts.meta.endpoint_url.startswith("https://sts")
    assert aws.session_for(CREDS, "us-east-1").region_name == "us-east-1"


# ───────────────────────── ECS / HTTP / tagging ─────────────────────────
class FakeAws:
    """One object answering the few ECS / tagging / secrets / RDS / logs calls verify.py makes."""

    def __init__(
        self, pages: list[list[str]], live: set[str] | None = None, stable: bool = True
    ) -> None:
        self.pages = pages
        self.live = live or set()
        self.stable = stable
        self.deleted: list[str] = []

    # tagging
    def get_resources(self, **kw: Any) -> dict[str, Any]:
        index = int(kw.get("PaginationToken") or 0)
        page: dict[str, Any] = {
            "ResourceTagMappingList": [{"ResourceARN": a} for a in self.pages[index]]
        }
        if index + 1 < len(self.pages):
            page["PaginationToken"] = str(index + 1)
        return page

    # ecs
    def get_waiter(self, name: str) -> Any:
        stable = self.stable

        class W:
            def wait(self, **kw: Any) -> None:
                if not stable:
                    raise WaiterError("services_stable", "timed out", {})

        return W()

    def describe_tasks(self, cluster: str, tasks: list[str]) -> dict[str, Any]:
        return {"tasks": [{"lastStatus": "RUNNING" if tasks[0] in self.live else "STOPPED"}]}

    def describe_task_definition(self, taskDefinition: str) -> dict[str, Any]:
        return {
            "taskDefinition": {
                "status": "INACTIVE" if taskDefinition in self.live else "DELETE_IN_PROGRESS"
            }
        }

    def list_task_definitions(self, familyPrefix: str, status: str) -> dict[str, Any]:
        return {"taskDefinitionArns": ["arn:td:1"] if status == "INACTIVE" else []}

    def deregister_task_definition(self, taskDefinition: str) -> None:
        raise _client_error("ClientException")  # already inactive

    def delete_task_definitions(self, taskDefinitions: list[str]) -> None:
        self.deleted += taskDefinitions

    # secrets / rds / logs
    def describe_secret(self, SecretId: str) -> dict[str, Any]:
        if SecretId not in self.live:
            raise _client_error("ResourceNotFoundException")
        return {}

    def describe_db_instances(self, DBInstanceIdentifier: str) -> dict[str, Any]:
        if not any(DBInstanceIdentifier in a for a in self.live):
            raise _client_error("DBInstanceNotFound")
        return {}

    def describe_log_groups(self, logGroupNamePrefix: str) -> dict[str, Any]:
        live = any(logGroupNamePrefix in a for a in self.live)
        return {"logGroups": [{"logGroupName": logGroupNamePrefix}] if live else []}


def test_wait_for_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "client", lambda s, svc, region=None: FakeAws([[]], stable=True))
    assert verify.wait_for_service(object(), "c", "s", 30)
    monkeypatch.setattr(verify, "client", lambda s, svc, region=None: FakeAws([[]], stable=False))
    assert not verify.wait_for_service(object(), "c", "s", 30)


def test_destroy_proof_separates_live_leftovers_from_a_lagging_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gone = [
        "arn:aws:ecs:us-east-1:1:task/cp-x-cluster/abc",
        "arn:aws:ecs:us-east-1:1:task-definition/cp-x-app:1",
        "arn:aws:secretsmanager:us-east-1:1:secret:cloudpilot/d/db-AbC",
        "arn:aws:rds:us-east-1:1:db:cp-x-db",
        "arn:aws:logs:us-east-1:1:log-group:/cloudpilot/d",
    ]
    fake = FakeAws([gone[:3], gone[3:]])
    monkeypatch.setattr(verify, "client", lambda s, svc, region=None: fake)
    check = verify.verify_destroyed(
        object(), "d", task_family="cp-x-app", timeout_s=0, sleep=lambda s: None
    )
    assert check.clean
    assert sorted(check.indexed_but_gone) == sorted(gone)
    assert check.deleted_task_definitions == 1
    assert fake.deleted == ["arn:td:1"]

    leftover = FakeAws([["arn:aws:ec2:us-east-1:1:vpc/vpc-1"]])
    monkeypatch.setattr(verify, "client", lambda s, svc, region=None: leftover)
    check = verify.verify_destroyed(
        object(), "d", task_family=None, timeout_s=0, sleep=lambda s: None
    )
    assert not check.clean
    assert check.remaining == ["arn:aws:ec2:us-east-1:1:vpc/vpc-1"]


# ───────────────────────── the runner loop ─────────────────────────
def test_runner_loop_claims_runs_one_job_and_exits(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = uuid.uuid4()
    seen: list[tuple[uuid.UUID, str]] = []
    monkeypatch.setattr(runner, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(runner, "sweep", lambda db: 0)
    claims = iter([None, (job_id, "plan")])
    monkeypatch.setattr(runner, "claim_next", lambda db, rid: next(claims))

    def execute(db: Session, deployment_id: uuid.UUID, action: str) -> str:
        seen.append((deployment_id, action))
        return "AWAITING_APPROVAL"

    monkeypatch.setattr(runner, "execute", execute)
    assert runner.run(once=True, poll_s=0) == 0
    assert seen == [(job_id, "plan")]


def test_runner_loop_stops_when_asked(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    monkeypatch.setattr(runner, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(runner, "sweep", lambda db: 0)

    def claim(db: Session, rid: str) -> None:
        stop.set()

    monkeypatch.setattr(runner, "claim_next", claim)
    assert runner.run(once=False, poll_s=0, stop=stop) == 0


def test_client_ip_trusts_forwarded_for_only_from_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.requests import Request

    from app.core.config import settings
    from app.core.ratelimit import client_ip

    def request(peer: str, forwarded: str) -> Request:
        return Request(
            {
                "type": "http",
                "client": (peer, 1),
                "headers": [(b"x-forwarded-for", forwarded.encode())],
            }
        )

    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.2")
    assert client_ip(request("10.0.0.2", "203.0.113.7, 10.0.0.2")) == "203.0.113.7"
    assert (
        client_ip(request("198.51.100.1", "203.0.113.7")) == "198.51.100.1"
    )  # spoofed header ignored
    assert client_ip(request("10.0.0.2", "not-an-ip")) == "10.0.0.2"


def test_egress_ip_is_detected_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.deployments import service

    calls: list[str] = []

    class Resp:
        text = "203.0.113.7\n"

    monkeypatch.setattr(service, "_egress_cache", None)

    def get(url: str, timeout: float) -> Resp:
        calls.append(url)
        return Resp()

    monkeypatch.setattr(service.httpx, "get", get)
    assert service.egress_ip().cidr == "203.0.113.7/32"
    assert service.egress_ip().ip == "203.0.113.7"
    assert calls == ["https://checkip.amazonaws.com"]
