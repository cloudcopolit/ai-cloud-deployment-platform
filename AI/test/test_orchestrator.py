import asyncio
from uuid import uuid4

from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.domain.analysis.blockers import Blocker
from AI.domain.shared.states import RunStatus
from AI.orchestration.graph import build_orchestrator
from AI.test.fakes import FakeAnalyzer, FakeStore, make_repo, make_report


def run(analyzer, store):
    graph = build_orchestrator(analyze=AnalyzeRepository(analyzer), store=store)
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