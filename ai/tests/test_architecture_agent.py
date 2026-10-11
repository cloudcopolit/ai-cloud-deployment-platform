"""Tests for the architecture proposal agent."""

import json

import pytest

from agents.architecture.agent import ArchitectureAgent
from agents.architecture.models import ArchitectureProposal
from agents.code_analyzer.repository_analyzer import analyze_repository
from workflows.repository import RepoSnapshot


class StubLLM:
    """Return a controlled response without making network calls."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.system = ""
        self.user = ""

    def complete(self, *, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return self.response


@pytest.fixture
def repository():
    """Create deterministic repository analysis for agent tests."""
    snapshot = RepoSnapshot(
        files={
            "app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "requirements.txt": "fastapi\n",
        }
    )
    return analyze_repository(snapshot, root_name="sample")


def valid_response() -> str:
    """Return a representative architecture proposal as JSON."""
    return json.dumps(
        {
            "project_name": "sample",
            "summary": "A small FastAPI application.",
            "components": [
                {
                    "name": "API",
                    "responsibility": "Expose application endpoints.",
                    "technology": "FastAPI",
                }
            ],
            "interactions": ["Clients send HTTP requests to the API."],
            "deployment_requirements": ["Provide a Python runtime."],
            "assumptions": ["The application will run as a web service."],
            "open_questions": ["Which cloud provider should be used?"],
        }
    )


def test_architecture_agent_parses_valid_response(repository):
    llm = StubLLM(valid_response())
    agent = ArchitectureAgent(llm)

    proposal = agent.run(repository, requirements="Deploy as a web API")

    assert isinstance(proposal, ArchitectureProposal)
    assert proposal.project_name == "sample"
    assert proposal.components[0].name == "API"
    assert proposal.components[0].technology == "FastAPI"
    assert proposal.open_questions == ("Which cloud provider should be used?",)
    assert "Deploy as a web API" in llm.user
    assert "architecture" in llm.system.lower()


def test_architecture_agent_rejects_invalid_json(repository):
    agent = ArchitectureAgent(StubLLM("not JSON"))

    with pytest.raises(ValueError, match="valid JSON"):
        agent.run(repository)


def test_architecture_agent_rejects_non_object_json(repository):
    agent = ArchitectureAgent(StubLLM('["not", "an", "object"]'))

    with pytest.raises(ValueError, match="JSON object"):
        agent.run(repository)


def test_architecture_agent_rejects_non_list_components(repository):
    response = json.loads(valid_response())
    response["components"] = {}
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="components.*list"):
        agent.run(repository)


def test_architecture_agent_rejects_invalid_component(repository):
    response = json.loads(valid_response())
    response["components"] = [{"name": "", "responsibility": "Serve requests"}]
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="name"):
        agent.run(repository)


def test_architecture_agent_rejects_invalid_string_lists(repository):
    response = json.loads(valid_response())
    response["interactions"] = ["valid", 123]
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="interactions"):
        agent.run(repository)


def test_architecture_agent_rejects_blank_summary(repository):
    response = json.loads(valid_response())
    response["summary"] = "   "
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="summary"):
        agent.run(repository)


def test_architecture_agent_rejects_invalid_technology_type(repository):
    response = json.loads(valid_response())
    response["components"][0]["technology"] = 123
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="technology"):
        agent.run(repository)


def test_architecture_agent_ignores_blank_response_project_name(repository):
    response = json.loads(valid_response())
    response["project_name"] = ""
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    proposal = agent.run(repository)

    assert proposal.project_name == repository.project_name


def test_architecture_agent_preserves_repository_project_name(repository):
    response = json.loads(valid_response())
    response["project_name"] = "unrelated-project"
    agent = ArchitectureAgent(StubLLM(json.dumps(response)))

    proposal = agent.run(repository)

    assert proposal.project_name == repository.project_name
    assert proposal.project_name != "unrelated-project"
