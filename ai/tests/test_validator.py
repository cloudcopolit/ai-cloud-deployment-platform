"""Comprehensive unit and integration tests for the Testing & Validation Agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from agents.code_analyzer.repository_analyzer import (
    AnalysisReport,
    RepositoryAnalysis,
)
from agents.orchestrator import Orchestrator
from agents.validator import (
    ErrorCategory,
    ScanTarget,
    StageResult,
    StageStatus,
    TestFailureDetail,
    TestMetrics,
    ValidationReport,
    ValidatorAgent,
    classify_error,
    extract_primary_error_message,
    parse_pytest_output,
    resolve_scan_target,
    run_runtime_smoke_test,
    scan_repository_standalone,
    stage_config,
)
from tools.process_runner import (
    run_command,
    start_process,
    terminate_process_tree,
)
from workflows.repository import RepoSnapshot


# ---------------------------------------------------------------------------
# 1. Pydantic v2 Models & Serialization
# ---------------------------------------------------------------------------


def test_validation_report_pydantic_v2_serialization():
    report = ValidationReport(
        project_name="demo-app",
        overall_status="passed",
        stages=(
            StageResult(
                stage_name="config_staging",
                status=StageStatus.PASSED,
                duration_seconds=0.01,
                output="Staged .env",
            ),
        ),
        test_metrics=TestMetrics(
            total=10,
            passed=9,
            failed=0,
            skipped=1,
            duration_seconds=1.25,
        ),
        test_failures=(),
        detected_entry_points=("main.py",),
        detected_frameworks=("FastAPI",),
        error_summary=(),
        total_duration_seconds=1.5,
    )

    dumped = report.model_dump()
    assert dumped["project_name"] == "demo-app"
    assert dumped["overall_status"] == "passed"
    assert dumped["test_metrics"]["total"] == 10
    assert dumped["test_metrics"]["passed"] == 9
    assert report.success is True

    json_str = report.model_dump_json(indent=2)
    parsed = json.loads(json_str)
    assert parsed["project_name"] == "demo-app"
    assert parsed["stages"][0]["stage_name"] == "config_staging"


# ---------------------------------------------------------------------------
# 2. Rule-Based Error Classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("log_sample", "expected_category"),
    [
        (
            "ModuleNotFoundError: No module named 'fastapi'",
            ErrorCategory.DEPENDENCY_ERROR,
        ),
        (
            "ImportError: cannot import name 'BaseSettings' from 'pydantic'",
            ErrorCategory.DEPENDENCY_ERROR,
        ),
        (
            "ERROR: Could not find a version that satisfies the requirement bogus-pkg",
            ErrorCategory.DEPENDENCY_ERROR,
        ),
        (
            "pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings\nDATABASE_URL\n  Field required",
            ErrorCategory.CONFIG_ERROR,
        ),
        (
            "KeyError: 'SECRET_KEY'",
            ErrorCategory.CONFIG_ERROR,
        ),
        (
            "ConnectionRefusedError: [Errno 111] Connection refused",
            ErrorCategory.RUNTIME_CRASH,
        ),
        (
            "OSError: [Errno 48] Address already in use",
            ErrorCategory.RUNTIME_CRASH,
        ),
        (
            "WinError 10048: Only one usage of each socket address is normally permitted",
            ErrorCategory.RUNTIME_CRASH,
        ),
        (
            "FAILED tests/test_app.py::test_math - AssertionError: assert 1 == 2",
            ErrorCategory.TEST_FAILURE,
        ),
        (
            "SyntaxError: invalid syntax (main.py, line 12)",
            ErrorCategory.BUILD_ERROR,
        ),
        (
            "IndentationError: unexpected indent",
            ErrorCategory.BUILD_ERROR,
        ),
        (
            "[TIMEOUT] Command timed out after 30 seconds.",
            ErrorCategory.TIMEOUT,
        ),
    ],
)
def test_error_classification_categories(log_sample: str, expected_category: ErrorCategory):
    category = classify_error(log_sample, exit_code=1)
    assert category == expected_category


def test_extract_primary_error_message():
    raw_tb = (
        "Traceback (most recent call last):\n"
        '  File "main.py", line 4, in <module>\n'
        "ModuleNotFoundError: No module named 'uvicorn'\n"
    )
    msg = extract_primary_error_message(raw_tb)
    assert msg == "ModuleNotFoundError: No module named 'uvicorn'"


# ---------------------------------------------------------------------------
# 3. Pytest Output Parsing
# ---------------------------------------------------------------------------


def test_parse_pytest_output_successful():
    stdout = "=== 5 passed in 0.45s ==="
    metrics, failures = parse_pytest_output(stdout, "")

    assert metrics.total == 5
    assert metrics.passed == 5
    assert metrics.failed == 0
    assert metrics.skipped == 0
    assert metrics.duration_seconds == 0.45
    assert len(failures) == 0


def test_parse_pytest_output_with_failures():
    stdout = (
        "FAILED tests/test_api.py::test_login - AssertionError: Status code 401 != 200\n"
        "____________________ test_login ____________________\n"
        "    def test_login():\n"
        ">       assert 401 == 200\n"
        "E       AssertionError: Status code 401 != 200\n"
        "tests/test_api.py:15: AssertionError\n"
        "=== 1 failed, 3 passed, 1 skipped in 1.10s ===\n"
    )
    metrics, failures = parse_pytest_output(stdout, "")

    assert metrics.total == 5
    assert metrics.passed == 3
    assert metrics.failed == 1
    assert metrics.skipped == 1
    assert metrics.duration_seconds == 1.10

    assert len(failures) == 1
    assert "test_login" in failures[0].test_name
    assert failures[0].category == ErrorCategory.TEST_FAILURE
    assert "AssertionError" in failures[0].traceback or "AssertionError" in failures[0].message


# ---------------------------------------------------------------------------
# 4. Config Staging (.env.example -> .env)
# ---------------------------------------------------------------------------


def test_stage_config_copies_example_template(tmp_path: Path):
    example_env = tmp_path / ".env.example"
    example_env.write_text("DB_HOST=localhost\nDB_PORT=5432\n", encoding="utf-8")

    result = stage_config(tmp_path)

    assert result.status == StageStatus.PASSED
    assert (tmp_path / ".env").exists()
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "DB_HOST=localhost\nDB_PORT=5432\n"


def test_stage_config_does_not_overwrite_existing_env(tmp_path: Path):
    existing_env = tmp_path / ".env"
    existing_env.write_text("EXISTING=true\n", encoding="utf-8")

    example_env = tmp_path / ".env.example"
    example_env.write_text("EXAMPLE=true\n", encoding="utf-8")

    result = stage_config(tmp_path)

    assert result.status == StageStatus.PASSED
    assert "Existing .env file detected" in result.output
    assert existing_env.read_text(encoding="utf-8") == "EXISTING=true\n"


def test_stage_config_skips_when_no_template_present(tmp_path: Path):
    result = stage_config(tmp_path)
    assert result.status == StageStatus.SKIPPED
    assert not (tmp_path / ".env").exists()


# ---------------------------------------------------------------------------
# 5. Scanner: Standalone Auto-Scan vs Guided Mode
# ---------------------------------------------------------------------------


def test_standalone_auto_scan(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("PORT=8000\n", encoding="utf-8")

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("print('hello')", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok(): pass", encoding="utf-8")

    target = scan_repository_standalone(tmp_path)

    assert target.is_guided is False
    assert "requirements.txt" in target.requirements_files
    assert "app/main.py" in target.entry_points
    assert "tests" in target.test_dirs
    assert ".env.example" in target.config_files
    assert "FastAPI" in target.frameworks
    assert "Uvicorn" in target.frameworks


def test_guided_mode_resolution(tmp_path: Path):
    (tmp_path / "server.py").write_text("app = None", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask", encoding="utf-8")

    analysis = RepositoryAnalysis(
        project_name="guided-proj",
        languages=("Python",),
        project_structure=("server.py",),
        entry_points=("server.py",),
        dependencies=("flask",),
        frameworks=("Flask",),
        config_files=("requirements.txt",),
        python_analysis=AnalysisReport(
            status="completed",
            files=(),
            total_files=1,
            parsed_files=1,
            syntax_error_files=0,
            skipped_files=0,
        ),
    )

    target = resolve_scan_target(tmp_path, analysis)

    assert target.is_guided is True
    assert target.project_name == "guided-proj"
    assert "server.py" in target.entry_points
    assert "Flask" in target.frameworks


# ---------------------------------------------------------------------------
# 6. Process Runner & Smoke Testing
# ---------------------------------------------------------------------------


def test_process_runner_run_command_and_timeout():
    # Fast successful command
    res = run_command([sys.executable, "-c", "print('Antigravity')"])
    assert res.exit_code == 0
    assert "Antigravity" in res.stdout
    assert res.timed_out is False

    # Command that times out
    res_timeout = run_command(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout=0.3,
    )
    assert res_timeout.timed_out is True
    assert "[TIMEOUT]" in res_timeout.stderr


def test_runtime_smoke_test_healthy_server(tmp_path: Path):
    server_file = tmp_path / "server.py"
    # A mock server that stays alive until killed
    server_file.write_text(
        "import time, sys\nsys.stdout.write('Booting...\\n')\nsys.stdout.flush()\ntime.sleep(10)\n",
        encoding="utf-8",
    )

    result = run_runtime_smoke_test(
        python_executable=sys.executable,
        repo_path=tmp_path,
        entry_point="server.py",
        frameworks=("FastAPI",),
        env={},
        grace_period=0.6,
    )

    assert result.status == StageStatus.PASSED
    assert "remained stable" in result.output


def test_runtime_smoke_test_crashed_server(tmp_path: Path):
    crashed_file = tmp_path / "crash.py"
    crashed_file.write_text(
        "import sys\nraise ConnectionRefusedError('Database unreachable at port 5432')\n",
        encoding="utf-8",
    )

    result = run_runtime_smoke_test(
        python_executable=sys.executable,
        repo_path=tmp_path,
        entry_point="crash.py",
        frameworks=("FastAPI",),
        env={},
        grace_period=2.0,
    )

    assert result.status == StageStatus.FAILED
    assert result.error_category == ErrorCategory.RUNTIME_CRASH
    assert "ConnectionRefusedError" in (result.error_message or "")


# ---------------------------------------------------------------------------
# 7. End-to-End ValidatorAgent Execution Pipeline
# ---------------------------------------------------------------------------


def test_validator_agent_end_to_end_passed(tmp_path: Path):
    # Setup a valid micro project
    (tmp_path / ".env.example").write_text("DEBUG=True\n", encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "import time\ntime.sleep(5)\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_core.py").write_text(
        "def test_success():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    agent = ValidatorAgent()
    report = agent.run(
        repo_path=tmp_path,
        skip_venv=True,  # reuse active test runner python
        python_executable=sys.executable,
        smoke_test_grace_period=0.5,
    )

    assert report.overall_status == "passed"
    assert report.success is True
    assert (tmp_path / ".env").exists()
    assert report.test_metrics is not None
    assert report.test_metrics.passed >= 1
    assert len(report.stages) == 5


def test_validator_agent_end_to_end_test_failure(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_fail.py").write_text(
        "def test_will_fail():\n    assert False, 'Expected value mismatch'\n",
        encoding="utf-8",
    )

    agent = ValidatorAgent()
    report = agent.run(
        repo_path=tmp_path,
        skip_venv=True,
        python_executable=sys.executable,
        smoke_test_grace_period=0.2,
    )

    assert report.overall_status == "failed"
    assert report.success is False
    assert report.test_metrics is not None
    assert report.test_metrics.failed >= 1
    assert len(report.test_failures) >= 1
    assert report.test_failures[0].category == ErrorCategory.TEST_FAILURE


# ---------------------------------------------------------------------------
# 8. Orchestrator Integration
# ---------------------------------------------------------------------------


def test_orchestrator_integrates_validator_agent(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text("def test_ok(): pass", encoding="utf-8")

    snapshot = RepoSnapshot(
        files={"main.py": "def main(): return 'ok'\n"}
    )

    validator = ValidatorAgent()
    orchestrator = Orchestrator(validator_agent=validator)

    # Calling run_repository with repo_path runs dynamic validation
    res = orchestrator.run_repository(
        snapshot,
        repo_path=str(tmp_path),
        validation_options={
            "skip_venv": True,
            "smoke_test_grace_period": 0.2,
        },
    )

    assert res.validation_status in ("passed", "failed")
    assert res.validation_report is not None
    assert res.validation_report.project_name == tmp_path.name
