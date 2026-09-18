from app.schemas import DeveloperIntent
from app.services.router import choose_initial_model, estimate_complexity


def test_simple_request_prefers_cheap():
    repo = "# FILE TREE\napp.py\n# FILE CONTENTS\n\n## FILE: app.py\nprint('hi')"
    intent = DeveloperIntent(goal="understand_architecture", depth="quick")
    decision = choose_initial_model(repo, intent)
    assert decision.tier == "cheap"


def test_complex_request_can_route_strong():
    repo = ("docker-compose kubernetes terraform postgres redis kafka " * 1000)
    intent = DeveloperIntent(
        goal="production_readiness",
        depth="production",
        scale="large_or_distributed",
        concerns=["security", "reliability", "scalability", "deployment"],
    )
    score, _ = estimate_complexity(repo, intent)
    assert score >= 5
    assert choose_initial_model(repo, intent).tier == "strong"
