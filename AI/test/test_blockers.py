from AI.domain.analysis.blockers import Blocker, evaluate_blockers
from AI.domain.analysis.models import ComponentSpec, ComponentType
from AI.test.fakes import make_report


def test_complete_report_has_no_blockers():
    assert evaluate_blockers(make_report()) == ()


def test_no_languages_is_a_blocker():
    assert Blocker.NO_RECOGNIZED_LANGUAGE in evaluate_blockers(make_report(languages=False))


def test_no_entry_point_is_a_blocker():
    assert Blocker.NO_ENTRY_POINT in evaluate_blockers(make_report(entry_points=False))


def test_more_than_three_components_is_a_blocker():
    comps = tuple(
        ComponentSpec(
            name=f"svc-{i}",
            root_dir=f"svc-{i}",
            type=ComponentType.SERVER,
            language="Python",
            start_cmd="python app.py",
        )
        for i in range(4)
    )
    report = make_report(components=comps)
    assert Blocker.TOO_MANY_COMPONENTS in evaluate_blockers(report)
