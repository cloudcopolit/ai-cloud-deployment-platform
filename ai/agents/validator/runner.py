"""Execution engine for dynamic verification stages."""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import venv
from pathlib import Path

from agents.validator.classifier import (
    classify_error,
    extract_primary_error_message,
)
from agents.validator.models import (
    ErrorCategory,
    ScanTarget,
    StageResult,
    StageStatus,
    TestFailureDetail,
    TestMetrics,
)
from tools.process_runner import (
    CommandResult,
    run_command,
    start_process,
    terminate_process_tree,
)

CONFIG_TEMPLATE_NAMES = (
    ".env.example",
    ".env.sample",
    ".env.template",
    "example.env",
)


def stage_config(repo_path: Path | str) -> StageResult:
    """Stage local configuration by copying .env.example/.env.sample to .env if absent."""
    root = Path(repo_path).resolve()
    env_file = root / ".env"
    start_time = time.monotonic()

    if env_file.exists():
        duration = round(time.monotonic() - start_time, 3)
        return StageResult(
            stage_name="config_staging",
            status=StageStatus.PASSED,
            duration_seconds=duration,
            output="Existing .env file detected; skipping template staging.",
        )

    for template_name in CONFIG_TEMPLATE_NAMES:
        template = root / template_name
        if template.is_file():
            try:
                shutil.copyfile(template, env_file)
                duration = round(time.monotonic() - start_time, 3)
                return StageResult(
                    stage_name="config_staging",
                    status=StageStatus.PASSED,
                    duration_seconds=duration,
                    output=f"Successfully copied configuration template '{template_name}' to '.env'.",
                )
            except OSError as exc:
                duration = round(time.monotonic() - start_time, 3)
                return StageResult(
                    stage_name="config_staging",
                    status=StageStatus.FAILED,
                    duration_seconds=duration,
                    output=f"Failed to copy template '{template_name}' to '.env': {exc}",
                    error_category=ErrorCategory.CONFIG_ERROR,
                    error_message=str(exc),
                )

    duration = round(time.monotonic() - start_time, 3)
    return StageResult(
        stage_name="config_staging",
        status=StageStatus.SKIPPED,
        duration_seconds=duration,
        output="No environment template (.env.example or .env.sample) found.",
    )


def provision_isolated_environment(
    repo_path: Path | str,
    venv_dir_name: str = ".venv_test_runner",
    clear: bool = False,
) -> tuple[StageResult, Path, dict[str, str]]:
    """Provision an isolated local virtual environment and construct the isolated execution PATH/PYTHONPATH."""
    root = Path(repo_path).resolve()
    venv_dir = root / venv_dir_name
    start_time = time.monotonic()

    try:
        builder = venv.EnvBuilder(with_pip=True, clear=clear)
        builder.create(venv_dir)

        if sys.platform == "win32":
            python_path = venv_dir / "Scripts" / "python.exe"
            scripts_dir = str(venv_dir / "Scripts")
            path_sep = ";"
        else:
            python_path = venv_dir / "bin" / "python"
            scripts_dir = str(venv_dir / "bin")
            path_sep = ":"

        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(venv_dir)
        env["PATH"] = f"{scripts_dir}{path_sep}{env.get('PATH', '')}"

        # Guarantee root repo imports resolve cleanly
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{root}{path_sep}{existing_pp}" if existing_pp else str(root)
        )

        duration = round(time.monotonic() - start_time, 3)
        result = StageResult(
            stage_name="environment_isolation",
            status=StageStatus.PASSED,
            duration_seconds=duration,
            output=f"Isolated virtual environment provisioned at {venv_dir}",
        )
        return result, python_path, env
    except Exception as exc:
        duration = round(time.monotonic() - start_time, 3)
        fallback_python = Path(sys.executable)
        result = StageResult(
            stage_name="environment_isolation",
            status=StageStatus.FAILED,
            duration_seconds=duration,
            output=f"Failed to provision virtual environment: {exc}",
            error_category=ErrorCategory.DEPENDENCY_ERROR,
            error_message=str(exc),
        )
        return result, fallback_python, os.environ.copy()


def install_dependencies(
    python_executable: Path | str,
    repo_path: Path | str,
    target: ScanTarget,
    env: dict[str, str],
    timeout: float = 300.0,
    ensure_pytest: bool = True,
) -> StageResult:
    """Install project dependencies into the isolated virtual environment using pip."""
    root = Path(repo_path).resolve()
    start_time = time.monotonic()

    py_str = str(python_executable)
    outputs: list[str] = []

    # 1. Install from discovered requirements files
    for req_file in target.requirements_files:
        p = root / req_file
        if req_file.endswith(".txt") and p.is_file():
            cmd = [py_str, "-m", "pip", "install", "-r", str(p)]
            res: CommandResult = run_command(
                cmd, cwd=root, env=env, timeout=timeout
            )
            outputs.append(f"pip install -r {req_file}:\n{res.stdout}\n{res.stderr}")
            if res.exit_code != 0:
                duration = round(time.monotonic() - start_time, 3)
                combined = f"{res.stdout}\n{res.stderr}"
                cat = classify_error(combined, res.exit_code)
                return StageResult(
                    stage_name="dependency_installation",
                    status=StageStatus.FAILED,
                    duration_seconds=duration,
                    exit_code=res.exit_code,
                    output="\n".join(outputs),
                    error_category=cat,
                    error_message=extract_primary_error_message(combined),
                )
        elif req_file == "pyproject.toml" and p.is_file():
            cmd = [py_str, "-m", "pip", "install", "-e", "."]
            res = run_command(cmd, cwd=root, env=env, timeout=timeout)
            outputs.append(f"pip install -e .:\n{res.stdout}\n{res.stderr}")
            if res.exit_code != 0:
                # Try non-editable install if editable fails
                cmd_fallback = [py_str, "-m", "pip", "install", "."]
                res_fallback = run_command(
                    cmd_fallback, cwd=root, env=env, timeout=timeout
                )
                outputs.append(f"pip install .:\n{res_fallback.stdout}\n{res_fallback.stderr}")
                if res_fallback.exit_code != 0:
                    duration = round(time.monotonic() - start_time, 3)
                    combined = f"{res_fallback.stdout}\n{res_fallback.stderr}"
                    cat = classify_error(combined, res_fallback.exit_code)
                    return StageResult(
                        stage_name="dependency_installation",
                        status=StageStatus.FAILED,
                        duration_seconds=duration,
                        exit_code=res_fallback.exit_code,
                        output="\n".join(outputs),
                        error_category=cat,
                        error_message=extract_primary_error_message(combined),
                    )

    # 2. Ensure pytest is installed in the test runner venv if test suites exist
    if ensure_pytest and target.test_dirs:
        res = run_command(
            [py_str, "-m", "pip", "install", "pytest"],
            cwd=root,
            env=env,
            timeout=120.0,
        )
        outputs.append(f"pip install pytest:\n{res.stdout}\n{res.stderr}")
        if res.exit_code != 0:
            duration = round(time.monotonic() - start_time, 3)
            combined = f"{res.stdout}\n{res.stderr}"
            cat = classify_error(combined, res.exit_code)
            return StageResult(
                stage_name="dependency_installation",
                status=StageStatus.FAILED,
                duration_seconds=duration,
                exit_code=res.exit_code,
                output="\n".join(outputs),
                error_category=cat,
                error_message=extract_primary_error_message(combined),
            )

    duration = round(time.monotonic() - start_time, 3)
    if not outputs:
        return StageResult(
            stage_name="dependency_installation",
            status=StageStatus.SKIPPED,
            duration_seconds=duration,
            output="No dependencies to install.",
        )

    return StageResult(
        stage_name="dependency_installation",
        status=StageStatus.PASSED,
        duration_seconds=duration,
        exit_code=0,
        output="\n".join(outputs),
    )


def parse_pytest_output(
    stdout: str, stderr: str
) -> tuple[TestMetrics, list[TestFailureDetail]]:
    """Parse pytest stdout and stderr using regex to extract structured metrics and failure details."""
    text = f"{stdout}\n{stderr}"

    # Extract metrics from summary line e.g. '= 2 passed, 1 failed, 1 skipped in 0.50s ='
    passed_m = re.search(r"(\d+)\s+passed", text)
    failed_m = re.search(r"(\d+)\s+failed", text)
    skipped_m = re.search(r"(\d+)\s+skipped", text)
    errors_m = re.search(r"(\d+)\s+error(?:s)?", text)
    duration_m = re.search(r"in\s+([\d\.]+)\s*s", text)

    passed = int(passed_m.group(1)) if passed_m else 0
    failed = int(failed_m.group(1)) if failed_m else 0
    skipped = int(skipped_m.group(1)) if skipped_m else 0
    errors = int(errors_m.group(1)) if errors_m else 0
    duration = float(duration_m.group(1)) if duration_m else 0.0

    total = passed + failed + skipped + errors
    metrics = TestMetrics(
        total=total,
        passed=passed,
        failed=failed + errors,
        skipped=skipped,
        duration_seconds=duration,
    )

    # Extract test failure details
    failures: list[TestFailureDetail] = []

    # Match FAILED lines: `FAILED tests/test_demo.py::test_case - AssertionError: foo`
    failed_lines = re.findall(r"^FAILED\s+([^\s\-]+)(?:\s+-\s+(.+))?$", text, re.MULTILINE)
    for test_name, msg in failed_lines:
        cat = classify_error(msg or test_name)
        failures.append(
            TestFailureDetail(
                test_name=test_name.strip(),
                message=(msg or "").strip(),
                category=cat,
            )
        )

    # Match detailed failure blocks if present
    # Pytest failure blocks usually start with `_{10,}\s*(.+?)\s*_{10,}`
    blocks = re.findall(r"_{10,}\s*(.+?)\s*_{10,}\n(.*?)(?=\n_{10,}|\n={5,}|\Z)", text, re.DOTALL)
    for block_name, block_content in blocks:
        clean_name = block_name.strip()
        cat = classify_error(block_content)
        # Check if already added via FAILED line
        matching = [f for f in failures if clean_name in f.test_name]
        if matching:
            # Enrich existing detail with traceback
            idx = failures.index(matching[0])
            failures[idx] = TestFailureDetail(
                test_name=matching[0].test_name,
                message=matching[0].message or extract_primary_error_message(block_content),
                traceback=block_content.strip()[:2000],
                category=cat,
            )
        else:
            failures.append(
                TestFailureDetail(
                    test_name=clean_name,
                    message=extract_primary_error_message(block_content),
                    traceback=block_content.strip()[:2000],
                    category=cat,
                )
            )

    return metrics, failures


def run_test_suite(
    python_executable: Path | str,
    repo_path: Path | str,
    target: ScanTarget,
    env: dict[str, str],
    timeout: float = 180.0,
) -> tuple[StageResult, TestMetrics, list[TestFailureDetail]]:
    """Execute test suites via pytest and extract structured metrics."""
    root = Path(repo_path).resolve()
    py_str = str(python_executable)
    start_time = time.monotonic()

    if not target.test_dirs:
        duration = round(time.monotonic() - start_time, 3)
        return (
            StageResult(
                stage_name="test_suite_execution",
                status=StageStatus.SKIPPED,
                duration_seconds=duration,
                output="No test directories detected in target repository.",
            ),
            TestMetrics(),
            [],
        )

    cmd = [py_str, "-m", "pytest", "-ra", "--tb=short"]
    res = run_command(cmd, cwd=root, env=env, timeout=timeout)
    duration = round(time.monotonic() - start_time, 3)

    combined_output = f"{res.stdout}\n{res.stderr}".strip()
    metrics, failures = parse_pytest_output(res.stdout, res.stderr)

    if res.exit_code == 0:
        stage_status = StageStatus.PASSED
        error_cat = None
        error_msg = None
    elif res.timed_out:
        stage_status = StageStatus.FAILED
        error_cat = ErrorCategory.TIMEOUT
        error_msg = f"Test execution timed out after {timeout} seconds."
    else:
        stage_status = StageStatus.FAILED
        error_cat = classify_error(combined_output, res.exit_code)
        error_msg = extract_primary_error_message(combined_output)

    result = StageResult(
        stage_name="test_suite_execution",
        status=stage_status,
        duration_seconds=duration,
        exit_code=res.exit_code,
        output=combined_output,
        error_category=error_cat,
        error_message=error_msg,
    )
    return result, metrics, failures


def run_runtime_smoke_test(
    python_executable: Path | str,
    repo_path: Path | str,
    entry_point: str,
    frameworks: tuple[str, ...],
    env: dict[str, str],
    grace_period: float = 5.0,
) -> StageResult:
    """Launch server entry points non-blocking, monitor for startup crashes, and cleanly kill the process tree."""
    root = Path(repo_path).resolve()
    entry_file = root / entry_point
    start_time = time.monotonic()

    if not entry_file.is_file():
        return StageResult(
            stage_name="runtime_smoke_test",
            status=StageStatus.SKIPPED,
            duration_seconds=0.0,
            output=f"Entry point '{entry_point}' not found on disk.",
        )

    # Determine command based on frameworks or python entry
    py_str = str(python_executable)
    cmd = [py_str, str(entry_file)]

    process = start_process(cmd, cwd=root, env=env)
    pid = process.pid

    # Monitor process health across the grace period
    deadline = time.monotonic() + grace_period
    crashed = False

    while time.monotonic() < deadline:
        poll_code = process.poll()
        if poll_code is not None:
            crashed = True
            break
        time.sleep(0.2)

    # Safely terminate the process tree to guarantee ports are not locked
    terminate_process_tree(pid)

    duration = round(time.monotonic() - start_time, 3)
    stdout, stderr = "", ""
    try:
        out, err = process.communicate(timeout=2.0)
        stdout, stderr = out or "", err or ""
    except Exception:
        pass

    combined = f"{stdout}\n{stderr}".strip()

    if crashed and process.returncode != 0:
        cat = classify_error(combined, process.returncode)
        msg = extract_primary_error_message(combined)
        return StageResult(
            stage_name="runtime_smoke_test",
            status=StageStatus.FAILED,
            duration_seconds=duration,
            exit_code=process.returncode,
            output=combined,
            error_category=cat,
            error_message=msg,
        )

    return StageResult(
        stage_name="runtime_smoke_test",
        status=StageStatus.PASSED,
        duration_seconds=duration,
        exit_code=0,
        output=f"Entry point '{entry_point}' successfully booted and remained stable for {grace_period}s grace period.",
    )
