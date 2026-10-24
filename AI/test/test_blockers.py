from AI.domain.analysis.blockers import Blocker, evaluate_blockers
from AI.test.fakes import make_report


def test_complete_report_has_no_blockers():
    assert evaluate_blockers(make_report()) == ()


def test_no_languages_is_a_blocker():
    assert Blocker.NO_RECOGNIZED_LANGUAGE in evaluate_blockers(make_report(languages=False))


def test_no_entry_point_is_a_blocker():
    assert Blocker.NO_ENTRY_POINT in evaluate_blockers(make_report(entry_points=False))