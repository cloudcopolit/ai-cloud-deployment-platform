"""The deploy runner (ADR-026/029/032): claims one deployment job, runs OpenTofu for it, and
exits. Compose restarts the container, so every job gets a fresh one.

    python -m app.deploy.runner --once

Jobs: QUEUED -> plan, APPLY_QUEUED -> apply + health check, DESTROY_QUEUED -> destroy + proof.
Every AWS call uses short-lived credentials from AssumeRole with the account's External ID.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cloudpilot_ai.architecture.pricing import load_prices
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import settings
from app.db.session import SessionLocal
from app.deploy import aws, policy, verify
from app.deploy.tofu import TofuError, Workspace, file_sha256
from app.models import (
    Approval,
    AWSAccount,
    Deployment,
    DeploymentStep,
    InfrastructureResource,
    Project,
)

logger = logging.getLogger("cloudpilot.deploy")

CLAIMABLE = {"QUEUED": "plan", "APPLY_QUEUED": "apply", "DESTROY_QUEUED": "destroy"}
RUNNING = {"plan": "PLANNING", "apply": "APPLYING", "destroy": "DESTROYING"}
ACTIVE = ("PLANNING", "APPLYING", "VERIFYING", "DESTROYING")


def _now() -> datetime:
    return datetime.now(UTC)


# ───────────────────────── queue ─────────────────────────
def claim_next(db: Session, runner_id: str) -> tuple[uuid.UUID, str] | None:
    job = db.scalar(
        select(Deployment)
        .where(Deployment.status.in_(list(CLAIMABLE)))
        .order_by(Deployment.created_at, Deployment.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.rollback()
        return None
    action = CLAIMABLE[job.status]
    now = _now()
    job.status = RUNNING[action]
    job.locked_by = runner_id
    job.attempts = (job.attempts or 0) + 1
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.deadline_at = now + timedelta(seconds=settings.deploy_job_timeout_s)
    db.commit()
    return job.id, action


def heartbeat(db: Session, deployment_id: uuid.UUID, runner_id: str) -> bool:
    row = db.execute(
        update(Deployment)
        .where(
            Deployment.id == deployment_id,
            Deployment.locked_by == runner_id,
            Deployment.status.in_(ACTIVE),
        )
        .values(heartbeat_at=_now())
    )
    db.commit()
    return bool(row.rowcount)  # type: ignore[attr-defined]


def sweep(db: Session) -> int:
    """Jobs whose runner disappeared end TIMED_OUT, honestly: infrastructure may exist, so
    destroy is offered. Never re-run an apply automatically."""
    stale = _now() - timedelta(seconds=settings.deploy_runner_stale_after_s)
    rows = db.scalars(
        select(Deployment)
        .where(Deployment.status.in_(ACTIVE), Deployment.heartbeat_at < stale)
        .with_for_update(skip_locked=True)
    ).all()
    for d in rows:
        was = d.status
        d.status = "TIMED_OUT" if was != "PLANNING" else "FAILED"
        d.error_code = "RUNNER_LOST"
        d.error_message = f"The deploy runner stopped responding while {was.lower()}."
        d.completed_at = _now()
        d.locked_by = None
    db.commit()
    return len(rows)


# ───────────────────────── tools (injectable for tests) ─────────────────────────
@dataclass
class Tools:
    assume: Callable[..., aws.TempCredentials] = aws.assume
    workspace: Callable[..., Workspace] = Workspace
    session_for: Callable[..., Any] = aws.session_for
    wait_for_service: Callable[..., bool] = verify.wait_for_service
    http_health: Callable[..., verify.HealthResult] = verify.http_health
    verify_destroyed: Callable[..., verify.CleanCheck] = verify.verify_destroyed
    s3_put: Callable[..., None] = field(default=None)  # type: ignore[assignment]
    s3_get: Callable[..., None] = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.s3_put is None:
            self.s3_put = _s3_put
        if self.s3_get is None:
            self.s3_get = _s3_get


def _s3_put(session: Any, bucket: str, key: str, path: Path) -> None:
    aws.client(session, "s3").upload_file(
        str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"}
    )


def _s3_get(session: Any, bucket: str, key: str, path: Path) -> None:
    aws.client(session, "s3").download_file(bucket, key, str(path))


# ───────────────────────── job context ─────────────────────────
@dataclass
class Job:
    db: Session
    deployment: Deployment
    account: AWSAccount
    project: Project
    action: str
    tools: Tools

    @property
    def variables(self) -> dict[str, Any]:
        return dict((self.deployment.config or {}).get("variables", {}))

    @property
    def region(self) -> str:
        return str(self.variables.get("region") or self.account.default_region)

    def step(
        self,
        name: str,
        status: str,
        *,
        output: dict | None = None,
        error: tuple[str, str] | None = None,
    ) -> None:
        row = self.db.scalar(
            select(DeploymentStep).where(
                DeploymentStep.deployment_id == self.deployment.id, DeploymentStep.step_type == name
            )
        )
        if row is None:
            return
        now = _now()
        if status == "RUNNING":
            row.started_at = now
            row.completed_at = None
            row.error_code = row.error_message = None
        elif status in {"SUCCESS", "FAILED", "SKIPPED"}:
            row.started_at = row.started_at or now
            row.completed_at = now
        row.status = status
        if output is not None:
            row.output_data = output
        if error is not None:
            row.error_code, row.error_message = error[0], error[1][:2000]
        self.db.commit()

    def audit(self, action: str, **details: Any) -> None:
        audit.record(
            self.db,
            team_id=self.project.team_id,
            action=action,
            target_type="deployment",
            target_id=self.deployment.id,
            plan_hash=self.deployment.plan_hash,
            details=details,
        )
        self.db.commit()

    def finish(self, status: str, *, error: tuple[str, str] | None = None) -> None:
        d = self.deployment
        d.status = status
        d.locked_by = None
        d.completed_at = _now()
        d.error_code, d.error_message = (error[0], error[1][:2000]) if error else (None, None)
        self.db.commit()

    def credentials(self) -> aws.TempCredentials:
        name = f"cp-{self.deployment.id.hex[:8]}-{self.action}-{self.deployment.attempts}"
        creds = self.tools.assume(
            self.account.role_arn,
            external_id=self.account.external_id,
            session_name=name,
            duration_s=3600,
        )
        self.deployment.sessions = [
            *(self.deployment.sessions or []),
            {"action": self.action, "session_name": name, "at": _now().isoformat()},
        ]
        self.db.commit()
        return creds

    def workspace(self, creds: aws.TempCredentials) -> Workspace:
        return self.tools.workspace(
            stack=(self.deployment.config or {}).get("stack", "container-postgres"),
            deployment_id=str(self.deployment.id),
            region=self.region,
            state_bucket=self.account.state_bucket,
            variables=self.variables,
            creds=creds,
        )


def _tail(exc: TofuError) -> dict[str, Any]:
    return {"exit_code": exc.code, "log_tail": exc.tail}


def _record_resources(job: Job, ws: Workspace, status: str) -> list[dict[str, str]]:
    found = ws.state_resources()
    db = job.db
    for row in db.scalars(
        select(InfrastructureResource).where(
            InfrastructureResource.deployment_id == job.deployment.id
        )
    ):
        db.delete(row)
    for r in found:
        db.add(
            InfrastructureResource(
                deployment_id=job.deployment.id,
                resource_type=r["type"],
                resource_name=r["address"][:255],
                aws_resource_id=r["id"][:255] or None,
                aws_arn=r["arn"] or None,
                region=job.region,
                status=status,
            )
        )
    db.commit()
    return found


# ───────────────────────── plan ─────────────────────────
def run_plan(job: Job) -> None:
    d = job.deployment
    job.step("PLAN", "RUNNING")
    creds = job.credentials()
    ws = job.workspace(creds)
    try:
        init = ws.init()
        plan_path, result = ws.plan()
        plan_json = ws.show_json(plan_path)
        plan_hash = file_sha256(plan_path)
        session = job.tools.session_for(creds, job.region)
        job.tools.s3_put(session, job.account.state_bucket, ws.plan_key(plan_hash), plan_path)
    except TofuError as exc:
        job.step("PLAN", "FAILED", output=_tail(exc), error=("PLAN_FAILED", str(exc)))
        job.finish("FAILED", error=("PLAN_FAILED", f"{exc}; see the plan step's log."))
        job.audit("PLAN_FAILED", exit_code=exc.code)
        return
    finally:
        ws.cleanup()

    summary = policy.summarize(plan_json)
    prices = load_prices(job.region)
    cost = policy.plan_cost(plan_json, prices)
    checks = policy.check_plan(
        plan_json,
        region=job.region,
        deployment_id=str(d.id),
        ingress_cidrs=list(job.variables.get("ingress_cidrs", [])),
        monthly_cost=cost["monthly_total"],
        monthly_cap=settings.deploy_monthly_cost_cap_usd,
    )
    d.plan_hash = plan_hash
    d.plan_summary = {
        "add": summary.add,
        "change": summary.change,
        "destroy": summary.destroy,
        "resources": summary.resources,
        "tofu_version": plan_json.get("terraform_version"),
        "plan_key": ws.plan_key(plan_hash),
    }
    d.cost_estimate = cost
    d.policy_results = policy.checks_json(checks)
    job.db.commit()
    job.step(
        "PLAN",
        "SUCCESS",
        output={
            "add": summary.add,
            "change": summary.change,
            "destroy": summary.destroy,
            "log_tail": result.tail[-25:] or init.tail[-10:],
        },
    )
    failed = [c for c in checks if not c.passed]
    job.step(
        "POLICY_CHECK",
        "FAILED" if failed else "SUCCESS",
        output={"checks": policy.checks_json(checks)},
        error=("POLICY_VIOLATION", "; ".join(c.message for c in failed)) if failed else None,
    )
    for old in job.db.scalars(
        select(Approval).where(Approval.deployment_id == d.id, Approval.status == "APPROVED")
    ):
        old.status = "SUPERSEDED"  # a new plan voids approvals of older plans (ADR-029)
    if failed:
        job.finish(
            "BLOCKED",
            error=("POLICY_VIOLATION", "The plan breaks a policy; it cannot be approved."),
        )
        job.audit("PLAN_BLOCKED", failed=[c.id for c in failed], monthly_cost=cost["monthly_total"])
    else:
        job.finish("AWAITING_APPROVAL")
        job.audit("PLAN_CREATED", add=summary.add, monthly_cost=cost["monthly_total"])


# ───────────────────────── apply ─────────────────────────
def _valid_approval(job: Job) -> Approval | None:
    approval = job.db.scalar(
        select(Approval)
        .where(Approval.deployment_id == job.deployment.id, Approval.status == "APPROVED")
        .order_by(Approval.decided_at.desc())
        .limit(1)
    )
    if (
        approval is None
        or approval.consumed_at is not None
        or approval.plan_hash != job.deployment.plan_hash
        or (approval.expires_at is not None and approval.expires_at < _now())
    ):
        return None
    return approval


def run_apply(job: Job) -> None:
    d = job.deployment
    approval = _valid_approval(job)
    if approval is None:  # fail closed (ADR-029)
        job.step(
            "APPLY", "FAILED", error=("APPROVAL_INVALID", "No valid approval for this exact plan.")
        )
        job.finish(
            "FAILED",
            error=("APPROVAL_INVALID", "No valid, unexpired approval for this exact plan."),
        )
        job.audit("APPLY_REFUSED", reason="approval invalid")
        return
    approval.status = "CONSUMED"
    approval.consumed_at = _now()
    job.db.commit()
    job.step("APPLY", "RUNNING")
    job.audit("APPLY_STARTED")
    creds = job.credentials()
    ws = job.workspace(creds)
    session = job.tools.session_for(creds, job.region)
    try:
        ws.init()
        local = ws.workdir / "approved.tfplan"
        job.tools.s3_get(session, job.account.state_bucket, ws.plan_key(d.plan_hash or ""), local)
        actual = file_sha256(local)
        if actual != d.plan_hash:
            job.step(
                "APPLY", "FAILED", error=("PLAN_HASH_MISMATCH", f"stored plan hashes to {actual}")
            )
            job.finish(
                "FAILED",
                error=(
                    "PLAN_HASH_MISMATCH",
                    "The stored plan does not match the approved hash; nothing was applied.",
                ),
            )
            job.audit("APPLY_REFUSED", reason="plan hash mismatch", actual=actual)
            return
        try:
            result = ws.apply(local)
        except TofuError as exc:
            found = _record_resources(job, ws, "FAILED")
            job.step(
                "APPLY",
                "FAILED",
                output={**_tail(exc), "resources_created": len(found)},
                error=("APPLY_FAILED", str(exc)),
            )
            job.finish(
                "FAILED",
                error=(
                    "APPLY_FAILED",
                    f"{exc}. {len(found)} resource(s) exist in AWS; destroy them from this page.",
                ),
            )
            job.audit("APPLY_FAILED", resources_created=len(found))
            return
        outputs = ws.outputs()
        found = _record_resources(job, ws, "ACTIVE")
        d.outputs = outputs
        job.db.commit()
        job.step(
            "APPLY", "SUCCESS", output={"log_tail": result.tail[-20:], "resources": len(found)}
        )
        job.audit("APPLY_SUCCEEDED", resources=len(found))
    finally:
        ws.cleanup()

    # health check (ADR-032): the infrastructure stays even if it fails
    d.status = "VERIFYING"
    job.db.commit()
    job.step("HEALTH_CHECK", "RUNNING")
    stable = job.tools.wait_for_service(
        session, outputs.get("cluster_name"), outputs.get("service_name"), 600
    )
    health = job.tools.http_health(str(outputs.get("health_url")), timeout_s=600)
    health.ecs_stable = stable
    d.health = health.json()
    job.db.commit()
    if health.passed:
        job.step("HEALTH_CHECK", "SUCCESS", output=health.json())
        job.finish("SUCCESS")
        job.audit(
            "HEALTH_CHECK_PASSED",
            url=health.url,
            status_code=health.status_code,
            attempts=health.attempts,
        )
    else:
        job.step(
            "HEALTH_CHECK",
            "FAILED",
            output=health.json(),
            error=("HEALTH_CHECK_FAILED", health.error or f"HTTP {health.status_code}"),
        )
        job.finish(
            "FAILED",
            error=(
                "HEALTH_CHECK_FAILED",
                f"{health.url} did not answer 2xx after {health.attempts} attempts; the "
                "infrastructure is still running. Destroy it or fix the app.",
            ),
        )
        job.audit(
            "HEALTH_CHECK_FAILED",
            url=health.url,
            status_code=health.status_code,
            attempts=health.attempts,
        )


# ───────────────────────── destroy ─────────────────────────
def run_destroy(job: Job) -> None:
    d = job.deployment
    job.step("DESTROY", "RUNNING")
    job.audit("DESTROY_STARTED")
    creds = job.credentials()
    ws = job.workspace(creds)
    session = job.tools.session_for(creds, job.region)
    try:
        ws.init()
        try:
            result = ws.destroy()
        except TofuError as exc:
            left = _record_resources(job, ws, "ACTIVE")
            job.step(
                "DESTROY",
                "FAILED",
                output={**_tail(exc), "remaining_in_state": len(left)},
                error=("DESTROY_FAILED", str(exc)),
            )
            job.finish(
                "DESTROY_FAILED",
                error=("DESTROY_FAILED", f"{exc}. {len(left)} resource(s) remain; retry destroy."),
            )
            job.audit("DESTROY_FAILED", remaining_in_state=len(left))
            return
        left = ws.state_resources()
    finally:
        ws.cleanup()
    job.step(
        "DESTROY",
        "SUCCESS",
        output={"log_tail": result.tail[-15:], "remaining_in_state": len(left)},
    )
    job.step("VERIFY_CLEAN", "RUNNING")
    family = (d.outputs or {}).get("task_family") or f"{job.variables.get('name_prefix')}-app"
    check = job.tools.verify_destroyed(session, str(d.id), task_family=family)
    d.destroy_check = {
        **check.json(),
        "remaining_in_state": len(left),
        "checked_at": _now().isoformat(),
    }
    for row in job.db.scalars(
        select(InfrastructureResource).where(InfrastructureResource.deployment_id == d.id)
    ):
        row.status = "DESTROYED" if check.clean and not left else row.status
    job.db.commit()
    if check.clean and not left:
        job.step("VERIFY_CLEAN", "SUCCESS", output=d.destroy_check)
        job.finish("DESTROYED")
        job.audit("DESTROYED", tagged_remaining=0, indexed_but_gone=len(check.indexed_but_gone))
    else:
        job.step(
            "VERIFY_CLEAN",
            "FAILED",
            output=d.destroy_check,
            error=("RESOURCES_REMAIN", ", ".join(check.remaining)[:1500]),
        )
        job.finish(
            "DESTROY_FAILED",
            error=(
                "RESOURCES_REMAIN",
                f"{len(check.remaining)} tagged resource(s) still exist; retry destroy.",
            ),
        )
        job.audit("DESTROY_FAILED", tagged_remaining=len(check.remaining))


ACTIONS: dict[str, Callable[[Job], None]] = {
    "plan": run_plan,
    "apply": run_apply,
    "destroy": run_destroy,
}


def execute(db: Session, deployment_id: uuid.UUID, action: str, tools: Tools | None = None) -> str:
    deployment = db.get(Deployment, deployment_id)
    assert deployment is not None  # noqa: S101 - claimed just before
    account = db.get(AWSAccount, deployment.aws_account_id)
    project = db.get(Project, deployment.project_id)
    if account is None or project is None or account.status != "ACTIVE":
        deployment.status = "FAILED"
        deployment.error_code = "ACCOUNT_NOT_ACTIVE"
        deployment.error_message = "The AWS account is missing or no longer verified."
        deployment.locked_by = None
        db.commit()
        return deployment.status
    job = Job(db, deployment, account, project, action, tools or Tools())
    try:
        ACTIONS[action](job)
    except Exception as exc:  # truthful state, never a silent RUNNING
        logger.exception("deploy job failed", extra={"deployment_id": str(deployment_id)})
        db.rollback()
        deployment = db.get(Deployment, deployment_id)
        if deployment is not None:
            failed = "DESTROY_FAILED" if action == "destroy" else "FAILED"
            deployment.status = failed
            deployment.error_code = "RUNNER_ERROR"
            deployment.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
            deployment.locked_by = None
            deployment.completed_at = _now()
            db.commit()
    if deployment is None:
        return "FAILED"
    db.refresh(deployment)
    return deployment.status


def run(*, once: bool, poll_s: float = 3.0, stop: threading.Event | None = None) -> int:
    runner_id = f"{socket.gethostname()}-{os.getpid()}"
    stop = stop or threading.Event()
    while not stop.is_set():
        with SessionLocal() as db:
            sweep(db)
            claimed = claim_next(db, runner_id)
        if claimed is None:
            stop.wait(poll_s)
            continue
        deployment_id, action = claimed
        logger.info(
            "claimed deployment job", extra={"deployment_id": str(deployment_id), "action": action}
        )
        beat_stop = threading.Event()

        def beat(stop_beat: threading.Event = beat_stop, job_id: uuid.UUID = deployment_id) -> None:
            while not stop_beat.wait(10):
                with SessionLocal() as hb:
                    heartbeat(hb, job_id, runner_id)

        beater = threading.Thread(target=beat, daemon=True)
        beater.start()
        try:
            with SessionLocal() as db:
                status = execute(db, deployment_id, action)
        finally:
            beat_stop.set()
            beater.join(timeout=5)
        logger.info(
            "deployment job finished", extra={"deployment_id": str(deployment_id), "status": status}
        )
        if once:
            return 0
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="exit after one job (a fresh container per job)"
    )
    args = parser.parse_args()
    if not aws.deploy_enabled():
        logger.warning("CLOUDPILOT_AWS_* not set: deployments are disabled; idling")
        threading.Event().wait()
    return run(once=args.once)


if __name__ == "__main__":
    sys.exit(main())
