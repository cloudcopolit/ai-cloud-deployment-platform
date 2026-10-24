import asyncio
from uuid import uuid4

from AI.agents.validator.agent import RepositoryManifestValidator
from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import (
    ComponentSpec,
    ComponentType,
    Evidence,
)
from AI.domain.shared.states import RunStatus
from AI.orchestration.graph import build_orchestrator
from AI.test.fakes import (
    FakeAnalyzer,
    FakeRepositoryReader,
    FakeStore,
    make_repo,
    make_report,
)


def run(analyzer, store, validator=None):
    graph = build_orchestrator(
        analyze=AnalyzeRepository(analyzer),
        store=store,
        validator=validator,
    )
    run_id = uuid4()
    asyncio.run(graph.ainvoke({"run_id": run_id, "repo": make_repo()}))
    return run_id


def test_complete_analysis_succeeds_and_saves_report():
    store = FakeStore()
    run(FakeAnalyzer(), store)

    assert store.statuses == [(RunStatus.SUCCEEDED, None)]
    assert len(store.saved) == 1
    _, report, blockers = store.saved[0]
    assert report.repo == make_repo()
    assert blockers == ()


def test_incomplete_analysis_is_blocked_and_still_saved():
    store = FakeStore()
    run(FakeAnalyzer(report=make_report(entry_points=False)), store)

    assert store.statuses == [(RunStatus.BLOCKED, None)]
    _, _, blockers = store.saved[0]
    assert blockers == (Blocker.NO_ENTRY_POINT,)


def test_analyzer_error_fails_run_without_saving():
    store = FakeStore()
    run(FakeAnalyzer(error=RuntimeError("model timeout")), store)

    assert store.statuses == [(RunStatus.FAILED, "analysis_failed")]
    assert store.saved == []


def test_error_message_is_not_stored_only_error_code():
    store = FakeStore()
    run(FakeAnalyzer(error=RuntimeError("secret-token-abc")), store)

    _, error_code = store.statuses[-1]
    assert error_code == "analysis_failed"
    assert "secret-token-abc" not in str(store.statuses)


def test_validator_retries_analysis_on_invalid_evidence_and_succeeds():
    bad_comp = ComponentSpec(
        name="api",
        root_dir=".",
        type=ComponentType.SERVER,
        language="Python",
        start_cmd="uvicorn main:app --port 8000",
        port=9999,  # Hallucinated port not in main.py
        evidence=(
            Evidence(field="port", file="non_existent.py", lines=(1, 1)),
            Evidence(field="start_cmd", file="Dockerfile", lines=(3, 3)),
        ),
        field_confidence={"port": 0.8, "start_cmd": 0.95},
    )
    bad_report = make_report(components=(bad_comp,))
    good_report = make_report()

    analyzer = FakeAnalyzer(reports_sequence=[bad_report, good_report])
    validator = RepositoryManifestValidator(FakeRepositoryReader())
    store = FakeStore()

    run(analyzer, store, validator=validator)

    assert len(analyzer.calls) == 2
    # Second call received validation feedback from the Validator Agent
    assert len(analyzer.calls[1][1]) > 0
    assert "non_existent.py" in analyzer.calls[1][1][0]
    assert store.statuses == [(RunStatus.SUCCEEDED, None)]


def test_validator_demotes_unverified_field_to_open_question_after_max_retries():
    bad_comp = ComponentSpec(
        name="api",
        root_dir=".",
        type=ComponentType.SERVER,
        language="Python",
        start_cmd="uvicorn main:app --port 8000",
        port=9999,  # Never verified across retries
        evidence=(
            Evidence(field="port", file="missing.py", lines=(1, 1)),
            Evidence(field="start_cmd", file="Dockerfile", lines=(3, 3)),
        ),
        field_confidence={"port": 0.8, "start_cmd": 0.95},
    )
    bad_report = make_report(components=(bad_comp,))

    analyzer = FakeAnalyzer(report=bad_report)
    validator = RepositoryManifestValidator(FakeRepositoryReader())
    store = FakeStore()

    run(analyzer, store, validator=validator)

    # Initial attempt + 2 bounded retries = 3 calls
    assert len(analyzer.calls) == 3
    assert store.statuses == [(RunStatus.AWAITING_INPUT, None)]
    _, saved_manifest, _ = store.saved[0]
    assert saved_manifest.components[0].port is None
    assert saved_manifest.components[0].confidence_for("port") == 0.0
    assert any(q.field_path == "api.port" for q in saved_manifest.open_questions)
