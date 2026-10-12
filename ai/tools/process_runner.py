"""Safe cross-platform subprocess execution and process tree termination."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of a managed subprocess execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


def terminate_process_tree(pid: int, timeout: float = 5.0) -> None:
    """Forcefully and cleanly terminate a process and all its spawned child processes."""
    if pid <= 0:
        return

    if sys.platform == "win32":
        try:
            # taskkill /F /T /PID terminates the process and all child processes
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=timeout,
            )
        except (subprocess.SubprocessError, OSError):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    else:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    # Check if process group is still present
                    os.killpg(pgid, 0)
                    time.sleep(0.1)
                except OSError:
                    return
            # Force kill if still lingering
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def run_command(
    cmd: Sequence[str] | str,
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    shell: bool = False,
) -> CommandResult:
    """Execute a subprocess command with timeout and process-group isolation."""
    cwd_str = str(cwd) if cwd is not None else None
    start_time = time.monotonic()

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd_str,
            env=env,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        stdout, stderr = process.communicate(timeout=timeout)
        duration = round(time.monotonic() - start_time, 3)
        return CommandResult(
            exit_code=process.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_seconds=duration,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - start_time, 3)
        if process is not None:
            terminate_process_tree(process.pid)
            stdout = (exc.stdout or "").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or "").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        else:
            stdout, stderr = "", ""

        return CommandResult(
            exit_code=-1,
            stdout=stdout,
            stderr=stderr + f"\n[TIMEOUT] Command timed out after {timeout} seconds.",
            duration_seconds=duration,
            timed_out=True,
        )
    except Exception as exc:
        duration = round(time.monotonic() - start_time, 3)
        if process is not None:
            terminate_process_tree(process.pid)
        return CommandResult(
            exit_code=-1,
            stdout="",
            stderr=f"[ERROR] Failed to execute command: {exc}",
            duration_seconds=duration,
            timed_out=False,
        )


def start_process(
    cmd: Sequence[str] | str,
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> subprocess.Popen[str]:
    """Spawn a non-blocking process in an isolated process group for monitoring."""
    cwd_str = str(cwd) if cwd is not None else None
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    return subprocess.Popen(
        cmd,
        cwd=cwd_str,
        env=env,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
