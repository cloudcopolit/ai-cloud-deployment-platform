import json

import pytest
from cloudpilot_ai.contracts import (
    AnalysisMeta,
    AnalysisReport,
    CostEstimate,
    Evidence,
    RepositoryRef,
)
from pydantic import ValidationError


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

    assert Evidence.model_validate(metadata).content_sha256 == "a" * 64
    with pytest.raises(ValidationError):
        Evidence.model_validate({**metadata, "excerpt": "source code"})


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


def test_self_check_block_still_holds() -> None:
    """The module's own `python contracts.py` self-check must keep passing."""
    import runpy

    import cloudpilot_ai.contracts as contracts

    runpy.run_path(contracts.__file__, run_name="__main__")


def test_plan_cannot_waive_human_approval() -> None:
    from uuid import UUID

    from cloudpilot_ai.contracts import (
        ArchitecturePlan,
        Component,
        ComponentType,
        CostLine,
        SecurityDesign,
    )

    plan = ArchitecturePlan(
        source_analysis_id=UUID(int=1),
        region="eu-central-1",
        components=[Component(id="api", type=ComponentType.ECS_SERVICE, rationale="runs the API")],
        security=SecurityDesign(
            network_isolation="private subnets",
            encryption_at_rest=True,
            encryption_in_transit=True,
            secrets_strategy="Secrets Manager",
        ),
        cost=CostEstimate(
            monthly_total=1.0,
            lines=[CostLine(component_id="api", monthly_usd=1.0, basis="x")],
            pricing_as_of="2026-10-01",
            confidence=0.5,
        ),
    )
    with pytest.raises(ValidationError):
        ArchitecturePlan.model_validate({**plan.model_dump(), "requires_human_approval": False})
