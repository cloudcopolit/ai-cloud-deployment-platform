"""AWS sessions (ADR-028): CloudPilot's own identity comes only from CLOUDPILOT_AWS_*; customer
access is always STS AssumeRole with the account's External ID, for one job at a time.
Credentials are never logged, stored or returned by the API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

# ignore_configured_endpoint_urls: the containers' AWS_ENDPOINT_URL points at LocalStack and
# boto3 would otherwise send CloudPilot's real identity there (ADR-028)
_BOTO = Config(
    retries={"max_attempts": 5, "mode": "standard"},
    connect_timeout=10,
    read_timeout=60,
    ignore_configured_endpoint_urls=True,
)


class DeployUnavailable(RuntimeError):
    """CloudPilot has no AWS identity configured: deployments are disabled."""


@dataclass(frozen=True)
class TempCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: datetime
    session_name: str

    def env(self) -> dict[str, str]:
        """For the OpenTofu process only."""
        return {
            "AWS_ACCESS_KEY_ID": self.access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
            "AWS_SESSION_TOKEN": self.session_token,
        }

    def __repr__(self) -> str:  # never print the secret parts
        return f"TempCredentials(session_name={self.session_name!r}, expiration={self.expiration})"


def deploy_enabled() -> bool:
    return bool(settings.cloudpilot_aws_access_key_id and settings.cloudpilot_aws_secret_access_key)


def platform_session() -> boto3.session.Session:
    if not deploy_enabled():
        raise DeployUnavailable("CloudPilot's AWS identity (CLOUDPILOT_AWS_*) is not configured.")
    return boto3.session.Session(
        aws_access_key_id=settings.cloudpilot_aws_access_key_id,
        aws_secret_access_key=settings.cloudpilot_aws_secret_access_key,
        region_name=settings.cloudpilot_aws_region,
    )


def client(session: boto3.session.Session, service: str, region: str | None = None) -> Any:
    return session.client(
        service,
        region_name=region or session.region_name,
        endpoint_url=settings.cloudpilot_aws_endpoint_url or None,
        config=_BOTO,
    )


def platform_principal_arn() -> str:
    """The ARN customers trust in the onboarding template."""
    identity = client(platform_session(), "sts").get_caller_identity()
    return str(identity["Arn"])


def assume(
    role_arn: str, *, external_id: str | None, session_name: str, duration_s: int = 3600
) -> TempCredentials:
    kwargs: dict[str, object] = {
        "RoleArn": role_arn,
        "RoleSessionName": session_name[:64],
        "DurationSeconds": duration_s,
    }
    if external_id is not None:
        kwargs["ExternalId"] = external_id
    creds = client(platform_session(), "sts").assume_role(**kwargs)["Credentials"]
    return TempCredentials(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        expiration=creds["Expiration"],
        session_name=session_name[:64],
    )


def session_for(creds: TempCredentials, region: str) -> boto3.session.Session:
    return boto3.session.Session(
        aws_access_key_id=creds.access_key_id,
        aws_secret_access_key=creds.secret_access_key,
        aws_session_token=creds.session_token,
        region_name=region,
    )


@dataclass(frozen=True)
class Verification:
    ok: bool
    identity_arn: str | None
    external_id_enforced: bool | None
    state_bucket_ok: bool | None
    message: str


def verify_account(
    *,
    account_id: str,
    role_arn: str,
    external_id: str,
    state_bucket: str,
    region: str,
    session_name: str,
) -> Verification:
    """Real STS AssumeRole with the External ID; then prove the External ID is required and
    the state bucket is reachable with the assumed role."""
    try:
        creds = assume(role_arn, external_id=external_id, session_name=session_name, duration_s=900)
    except (ClientError, BotoCoreError) as exc:
        code = exc.response["Error"]["Code"] if isinstance(exc, ClientError) else type(exc).__name__
        return Verification(
            False, None, None, None, f"AssumeRole with the External ID failed ({code})."
        )
    session = session_for(creds, region)
    identity = client(session, "sts").get_caller_identity()
    if identity["Account"] != account_id:
        return Verification(
            False,
            identity["Arn"],
            None,
            None,
            f"The role belongs to account {identity['Account']}, not {account_id}.",
        )
    try:
        assume(role_arn, external_id=None, session_name=f"{session_name}-noext", duration_s=900)
        enforced = False
    except ClientError as exc:
        enforced = exc.response["Error"]["Code"] in {"AccessDenied", "AccessDeniedException"}
    try:
        client(session, "s3").head_bucket(Bucket=state_bucket)
        bucket_ok = True
    except ClientError:
        bucket_ok = False
    if not enforced:
        return Verification(
            False,
            identity["Arn"],
            False,
            bucket_ok,
            "The role can be assumed WITHOUT the External ID; redeploy the onboarding template.",
        )
    if not bucket_ok:
        return Verification(
            False,
            identity["Arn"],
            True,
            False,
            f"The state bucket {state_bucket} is not reachable with the role.",
        )
    return Verification(True, identity["Arn"], True, True, "Verified.")
