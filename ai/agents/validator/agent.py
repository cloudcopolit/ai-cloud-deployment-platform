"""Testing & Validation Agent executing deterministic dynamic verification."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from agents.code_analyzer.repository_analyzer import RepositoryAnalysis
from agents.validator.models import (
    ScanTarget,
    StageResult,
    StageStatus,
    TestFailureDetail,
    TestMetrics,
    ValidationReport,
)
from agents.validator.runner import (
    install_dependencies,
    provision_isolated_environment,
    run_runtime_smoke_test,
    run_test_suite,
    stage_config,
)
from agents.validator.scanner import resolve_scan_target


class ValidatorAgent:
    """Dynamic testing and verification agent for repository execution and health verification."""

    def run(
        self,
        repo_path: Path | str,
        report_or_json: RepositoryAnalysis | dict[str, Any] | str | Path | None = None,
        *,
        skip_venv: bool = False,
        python_executable: Path | str | None = None,
        smoke_test_grace_period: float = 5.0,
        dependency_timeout: float = 300.0,
        test_timeout: float = 180.0,
    ) -> ValidationReport:
        """Execute the end-to-end 7-stage verification pipeline and return a structured Pydantic report."""
        root = Path(repo_path).resolve()
        start_time = time.monotonic()

        # Step 1: Resolve target via Guided Mode or Standalone Auto-Scan
        target: ScanTarget = resolve_scan_target(root, report_or_json)

        stages: list[StageResult] = []
        all_failures: list[TestFailureDetail] = []
        test_metrics: TestMetrics | None = None
        error_summary: list[str] = []

        # Stage 1: Config Staging (.env.example -> .env)
        stage_1 = stage_config(root)
        stages.append(stage_1)
        if stage_1.status == StageStatus.FAILED and stage_1.error_message:
            error_summary.append(f"Config Staging: {stage_1.error_message}")

        # Stage 2: Environment Isolation
        if skip_venv or python_executable is not None:
            active_python = Path(python_executable or sys.executable)
            env = os.environ.copy()
            path_sep = ";" if sys.platform == "win32" else ":"
            existing_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                f"{root}{path_sep}{existing_pp}" if existing_pp else str(root)
            )
            stages.append(
                StageResult(
                    stage_name="environment_isolation",
                    status=StageStatus.SKIPPED,
                    output=f"Using specified Python runtime: {active_python}",
                )
            )
        else:
            stage_2, active_python, env = provision_isolated_environment(root)
            stages.append(stage_2)
            if stage_2.status == StageStatus.FAILED and stage_2.error_message:
                error_summary.append(f"Environment Isolation: {stage_2.error_message}")

        # Stage 3: Dependency Installation
        if skip_venv:
            stages.append(
                StageResult(
                    stage_name="dependency_installation",
                    status=StageStatus.SKIPPED,
                    output="Skipped dependency installation (skip_venv=True).",
                )
            )
        else:
            stage_3 = install_dependencies(
                active_python,
                root,
                target,
                env,
                timeout=dependency_timeout,
            )
            stages.append(stage_3)
            if stage_3.status == StageStatus.FAILED and stage_3.error_message:
                error_summary.append(
                    f"Dependency Installation: {stage_3.error_message}"
                )

        # Stage 4: Test Suite Execution
        if target.test_dirs:
            stage_4, metrics, failures = run_test_suite(
                active_python,
                root,
                target,
                env,
                timeout=test_timeout,
            )
            stages.append(stage_4)
            test_metrics = metrics
            all_failures.extend(failures)
            if stage_4.status == StageStatus.FAILED and stage_4.error_message:
                error_summary.append(f"Test Suite: {stage_4.error_message}")
        else:
            stages.append(
                StageResult(
                    stage_name="test_suite_execution",
                    status=StageStatus.SKIPPED,
                    output="No test suites detected.",
                )
            )

        # Stage 5: Runtime Smoke Test
        if target.entry_points:
            primary_entry = target.entry_points[0]
            stage_5 = run_runtime_smoke_test(
                active_python,
                root,
                primary_entry,
                target.frameworks,
                env,
                grace_period=smoke_test_grace_period,
            )
            stages.append(stage_5)
            if stage_5.status == StageStatus.FAILED and stage_5.error_message:
                error_summary.append(f"Smoke Test: {stage_5.error_message}")
        else:
            stages.append(
                StageResult(
                    stage_name="runtime_smoke_test",
                    status=StageStatus.SKIPPED,
                    output="No server entry points detected for smoke testing.",
                )
            )

        # Calculate overall status
        failed_stages = [
            s for s in stages if s.status == StageStatus.FAILED
        ]
        if not failed_stages:
            overall_status = "passed"
        elif any(
            s.error_category in ("DEPENDENCY_ERROR", "BUILD_ERROR", "TIMEOUT")
            for s in failed_stages
        ):
            overall_status = "error"
        else:
            overall_status = "failed"

        total_duration = round(time.monotonic() - start_time, 3)

        return ValidationReport(
            project_name=target.project_name,
            overall_status=overall_status,
            stages=tuple(stages),
            test_metrics=test_metrics,
            test_failures=tuple(all_failures),
            detected_entry_points=target.entry_points,
            detected_frameworks=target.frameworks,
            error_summary=tuple(error_summary),
            total_duration_seconds=total_duration,
        )

    def validate(
        self,
        repo_path: Path | str,
        report_or_json: RepositoryAnalysis | dict[str, Any] | str | Path | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Alias for run method."""
        return self.run(repo_path, report_or_json, **kwargs)
