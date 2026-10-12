"""Pydantic v2 models for the dynamic testing and validation agent."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorCategory(StrEnum):
    """Standardized failure categories for code validation."""

    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    RUNTIME_CRASH = "RUNTIME_CRASH"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_ERROR = "BUILD_ERROR"
    TIMEOUT = "TIMEOUT"


class StageStatus(StrEnum):
    """Lifecycle status of an individual validation stage."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestMetrics(BaseModel):
    """Aggregated test suite execution statistics."""

    __test__ = False
    model_config = ConfigDict(frozen=True)

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0


class TestFailureDetail(BaseModel):
    """Detailed traceback and diagnostic information for a failed test."""

    __test__ = False
    model_config = ConfigDict(frozen=True)

    test_name: str
    message: str = ""
    traceback: str = ""
    category: ErrorCategory = ErrorCategory.TEST_FAILURE


class StageResult(BaseModel):
    """Result of an individual verification pipeline stage."""

    model_config = ConfigDict(frozen=True)

    stage_name: str
    status: StageStatus
    duration_seconds: float = 0.0
    exit_code: int | None = None
    output: str = ""
    error_category: ErrorCategory | None = None
    error_message: str | None = None


class ScanTarget(BaseModel):
    """Target project metadata resolved via guided input or standalone auto-scan."""

    model_config = ConfigDict(frozen=True)

    project_name: str = "unknown-project"
    repo_path: str
    requirements_files: tuple[str, ...] = Field(default_factory=tuple)
    entry_points: tuple[str, ...] = Field(default_factory=tuple)
    test_dirs: tuple[str, ...] = Field(default_factory=tuple)
    config_files: tuple[str, ...] = Field(default_factory=tuple)
    frameworks: tuple[str, ...] = Field(default_factory=tuple)
    is_guided: bool = False


class ValidationReport(BaseModel):
    """Structured dynamic validation report consumable by downstream agents."""

    model_config = ConfigDict(frozen=True)

    project_name: str
    overall_status: Literal["passed", "failed", "error"]
    stages: tuple[StageResult, ...] = Field(default_factory=tuple)
    test_metrics: TestMetrics | None = None
    test_failures: tuple[TestFailureDetail, ...] = Field(default_factory=tuple)
    detected_entry_points: tuple[str, ...] = Field(default_factory=tuple)
    detected_frameworks: tuple[str, ...] = Field(default_factory=tuple)
    error_summary: tuple[str, ...] = Field(default_factory=tuple)
    total_duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """Convenience property for downstream pipeline orchestrators."""
        return self.overall_status == "passed"
