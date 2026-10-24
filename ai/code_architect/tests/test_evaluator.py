from app.schemas import ArchitectureAnalysis, Component, Connection, DeveloperIntent, Recommendation
from app.services.evaluator import evaluate_analysis


def test_good_analysis_scores_well():
    analysis = ArchitectureAnalysis(
        project_name="Demo",
        summary="Production deployment with reliability and security considerations.",
        detected_stack=["FastAPI"],
        components=[
            Component(id="api", name="API", type="backend", technology="FastAPI", description="API", evidence=["app/main.py"]),
            Component(id="db", name="DB", type="database", technology="PostgreSQL", description="DB", evidence=["docker-compose.yml"]),
        ],
        connections=[Connection(source="api", target="db", protocol="SQL")],
        recommendations=[
            Recommendation(title="Improve reliability", priority="high", rationale="Add health checks for production."),
            Recommendation(title="Improve security", priority="high", rationale="Move credentials to secrets."),
            Recommendation(title="Improve deployment", priority="medium", rationale="Add CI/CD."),
        ],
    )
    intent = DeveloperIntent(goal="production_readiness", depth="deep", concerns=["reliability", "security", "deployment"])
    report = evaluate_analysis(analysis, intent)
    assert report.evidence_coverage == 1.0
    assert report.connection_validity == 1.0
    assert report.score >= 0.75
