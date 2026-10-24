import asyncio

import pytest

from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.domain.analysis.models import RepositoryRef
from AI.domain.shared.errors import AnalysisFailedError
from AI.test.fakes import FakeAnalyzer, make_repo, make_report


def test_returns_outcome_with_no_blockers_for_complete_report():
    outcome = asyncio.run(AnalyzeRepository(FakeAnalyzer()).execute(make_repo()))
    assert outcome.blockers == ()
    assert outcome.is_blocked is False


def test_reports_blockers_when_report_is_incomplete():
    analyzer = FakeAnalyzer(report=make_report(entry_points=False))
    outcome = asyncio.run(AnalyzeRepository(analyzer).execute(make_repo()))
    assert outcome.is_blocked is True


def test_rejects_report_for_a_different_commit():
    wrong = make_report(RepositoryRef("acme", "api", "zzz999"))
    use_case = AnalyzeRepository(FakeAnalyzer(report=wrong))
    with pytest.raises(AnalysisFailedError):
        asyncio.run(use_case.execute(make_repo()))