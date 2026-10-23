# ruff: noqa: S101
import json

import pytest
from pydantic import ValidationError

from project_context.contracts.ai_contracts import (
    AnalysisMeta,
    AnalysisReport,
    CostEstimate,
    Evidence,
    RepositoryRef,
)


def _repository() -> RepositoryRef:
    return RepositoryRef(
        owner="acme",
        name="demo-shop",
        branch="main",
        commit_sha="c3d4e5f60718293a4b5c6d7e8f90123456789012",
    )


def test_strict_contract_rejects_coerced_integer() -> None:
    payload = {
        "analyzer_version": "0.1.0",
        "files_scanned": "84",
        "files_skipped": 0,
        "duration_ms": 0,
    }
    with pytest.raises(ValidationError):
        AnalysisMeta.model_validate(payload)
    with pytest.raises(ValidationError):
        AnalysisMeta.model_validate_json(json.dumps(payload))


def test_evidence_contains_metadata_and_rejects_source_excerpt() -> None:
    metadata = {
        "file_path": "requirements.txt",
        "line_start": 1,
        "detector": "dependency_manifest",
        "content_sha256": "a" * 64,
    }

    assert Evidence(**metadata).content_sha256 == "a" * 64
    with pytest.raises(ValidationError):
        Evidence(**metadata, excerpt="source code")


def test_is_deployable_is_not_part_of_serialized_report() -> None:
    report = AnalysisReport(
        repository=_repository(),
        summary="FastAPI service",
        overall_confidence=0.9,
        meta=AnalysisMeta(
            analyzer_version="0.1.0",
            files_scanned=1,
            files_skipped=0,
            duration_ms=1,
        ),
    )

    serialized = report.model_dump()
    serialized_json = report.model_dump_json()
    assert report.is_deployable is True
    assert "is_deployable" not in serialized
    assert "is_deployable" not in serialized_json
    assert AnalysisReport.model_validate(serialized).is_deployable is True
    assert AnalysisReport.model_validate_json(serialized_json).is_deployable is True


def test_empty_cost_lines_require_zero_monthly_total() -> None:
    estimate = CostEstimate(
        monthly_total=0.0,
        lines=[],
        pricing_as_of="2026-10-24",
        confidence=0.5,
    )
    assert estimate.monthly_total == 0.0

    with pytest.raises(ValidationError, match="monthly_total must equal the sum of lines"):
        CostEstimate(
            monthly_total=30.0,
            lines=[],
            pricing_as_of="2026-10-24",
            confidence=0.5,
        )
