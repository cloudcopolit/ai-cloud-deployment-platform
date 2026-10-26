"""OpenTofu in a throwaway workspace (ADR-026/027).

The stack is copied from the image's read-only module library into a temp dir; the backend is
the customer's S3 bucket with native locking. The `tofu` process gets a minimal environment
built from scratch: the job's temporary credentials, the egress proxy, and nothing else from
the runner (never CloudPilot's own keys, never the LocalStack values).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.deploy.aws import TempCredentials

STACKS_DIR = Path(os.environ.get("CLOUDPILOT_STACKS_DIR", "/opt/cloudpilot/opentofu/stacks"))
TOFU = os.environ.get("TOFU_BIN", "tofu")
PASSTHROUGH = (
    "PATH",
    "TF_CLI_CONFIG_FILE",
    "TF_PLUGIN_CACHE_DIR",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
)
OUTPUT_TAIL = 60  # lines of tofu output kept per step (sanitized)

# Anything that looks like a credential is masked before output is stored or shown.
_SECRETISH = re.compile(
    r"(AKIA|ASIA)[A-Z0-9]{16}|(?i:(secret|password|token)[\"'=:\s]+)[^\s\"',]{8,}"
)


def sanitize(text: str) -> str:
    return _SECRETISH.sub(lambda m: (m.group(1) or m.group(2) or "") + "****", text)


class TofuError(RuntimeError):
    def __init__(self, step: str, code: int, tail: list[str]) -> None:
        super().__init__(f"tofu {step} failed (exit {code})")
        self.step = step
        self.code = code
        self.tail = tail


@dataclass
class RunResult:
    code: int
    tail: list[str] = field(default_factory=list)


@dataclass
class Workspace:
    stack: str
    deployment_id: str
    region: str
    state_bucket: str
    variables: dict[str, Any]
    creds: TempCredentials
    workdir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.workdir = Path(tempfile.mkdtemp(prefix="tofu-", dir=os.environ.get("TMPDIR")))
        shutil.copytree(STACKS_DIR / self.stack, self.workdir, dirs_exist_ok=True)
        (self.workdir / "cloudpilot.auto.tfvars.json").write_text(
            json.dumps(self.variables, indent=2), encoding="utf-8"
        )

    @property
    def state_key(self) -> str:
        return f"deployments/{self.deployment_id}/terraform.tfstate"

    def plan_key(self, plan_hash: str) -> str:
        return f"deployments/{self.deployment_id}/plans/{plan_hash}.tfplan"

    def _env(self) -> dict[str, str]:
        env = {k: os.environ[k] for k in PASSTHROUGH if k in os.environ}
        env.update(
            {
                "HOME": str(self.workdir),
                "TF_IN_AUTOMATION": "1",
                "TF_INPUT": "0",
                "CHECKPOINT_DISABLE": "1",
                "AWS_REGION": self.region,
                "AWS_DEFAULT_REGION": self.region,
                "AWS_EC2_METADATA_DISABLED": "true",
            }
        )
        env.update(self.creds.env())
        return env

    def run(self, step: str, args: list[str], *, timeout_s: int, check: bool = True) -> RunResult:
        proc = subprocess.run(  # noqa: S603 - fixed binary, arguments built here
            [TOFU, *args, "-no-color"],
            cwd=self.workdir,
            env=self._env(),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        lines = sanitize((proc.stdout or "") + (proc.stderr or "")).splitlines()
        result = RunResult(proc.returncode, lines[-OUTPUT_TAIL:])
        if check and proc.returncode != 0:
            raise TofuError(step, proc.returncode, result.tail)
        return result

    def init(self) -> RunResult:
        return self.run(
            "init",
            [
                "init",
                "-input=false",
                "-reconfigure",
                f"-backend-config=bucket={self.state_bucket}",
                f"-backend-config=key={self.state_key}",
                f"-backend-config=region={self.region}",
                "-backend-config=use_lockfile=true",
                "-backend-config=encrypt=true",
            ],
            timeout_s=300,
        )

    def plan(self) -> tuple[Path, RunResult]:
        path = self.workdir / "plan.tfplan"
        result = self.run(
            "plan", ["plan", "-input=false", "-lock-timeout=120s", f"-out={path}"], timeout_s=900
        )
        return path, result

    def show_json(self, plan: Path | None = None) -> dict[str, Any]:
        args = ["show", "-json"] + ([str(plan)] if plan else [])
        proc = subprocess.run(  # noqa: S603
            [TOFU, *args],
            cwd=self.workdir,
            env=self._env(),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if proc.returncode != 0:
            raise TofuError(
                "show", proc.returncode, sanitize(proc.stderr).splitlines()[-OUTPUT_TAIL:]
            )
        return json.loads(proc.stdout or "{}")

    def apply(self, plan: Path) -> RunResult:
        return self.run(
            "apply", ["apply", "-input=false", "-lock-timeout=120s", str(plan)], timeout_s=2700
        )

    def destroy(self) -> RunResult:
        return self.run(
            "destroy",
            ["destroy", "-input=false", "-auto-approve", "-lock-timeout=120s"],
            timeout_s=2700,
        )

    def outputs(self) -> dict[str, Any]:
        proc = subprocess.run(  # noqa: S603
            [TOFU, "output", "-json"],
            cwd=self.workdir,
            env=self._env(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            return {}
        raw = json.loads(proc.stdout or "{}")
        return {k: v.get("value") for k, v in raw.items() if not v.get("sensitive")}

    def state_resources(self) -> list[dict[str, str]]:
        """Managed resources that exist now (from state), for truthful partial-failure reports."""
        try:
            state = self.show_json()
        except TofuError:
            return []
        found: list[dict[str, str]] = []

        def walk(module: dict[str, Any]) -> None:
            for r in module.get("resources", []):
                if r.get("mode") != "managed":
                    continue
                values = r.get("values") or {}
                found.append(
                    {
                        "address": r["address"],
                        "type": r["type"],
                        "id": str(values.get("id") or ""),
                        "arn": str(values.get("arn") or ""),
                    }
                )
            for child in module.get("child_modules", []):
                walk(child)

        walk(state.get("values", {}).get("root_module", {}))
        return found

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
