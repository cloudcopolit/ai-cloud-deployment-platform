from app.schemas import ArchitectureAnalysis, Component, Connection
from app.services.mermaid import architecture_to_mermaid


def test_mermaid_generation():
    analysis = ArchitectureAnalysis(
        project_name="Demo",
        summary="Demo",
        detected_stack=["React", "FastAPI"],
        components=[
            Component(id="ui", name="UI", type="frontend", technology="React", description="Frontend"),
            Component(id="api", name="API", type="backend", technology="FastAPI", description="Backend"),
        ],
        connections=[Connection(source="ui", target="api", protocol="HTTPS")],
        recommendations=[],
        assumptions=[],
    )
    result = architecture_to_mermaid(analysis)
    assert "flowchart LR" in result
    assert 'ui -->|"HTTPS"| api' in result
