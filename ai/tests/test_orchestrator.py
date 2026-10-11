import json

from agents.architecture.agent import ArchitectureAgent
from agents.architecture.models import ArchitectureProposal
from agents.orchestrator import Orchestrator
from workflows.repository import RepoSnapshot


class StubArchitectureLLM:
    """Return a deterministic architecture proposal for testing."""

    def complete(self, *, system: str, user: str) -> str:
        return json.dumps(
            {
                "project_name": "sample",
                "summary": "A simple web application.",
                "components": [
                    {
                        "name": "API",
                        "responsibility": "Handle HTTP requests.",
                        "technology": "FastAPI",
                    }
                ],
                "interactions": ["Clients communicate with the API over HTTP."],
                "deployment_requirements": ["Python runtime"],
                "assumptions": [],
                "open_questions": ["Which cloud provider should be used?"],
            }
        )


def test_orchestrator_analyzes_valid_python():
    sources = {"main.py": "def main():\n    return 'hello'\n"}

    result = Orchestrator().run(sources)

    assert result.analysis.status == "completed"
    assert result.validation_status == "not_run"


def test_orchestrator_reports_syntax_errors():
    sources = {"main.py": "def main(:\n    pass\n"}

    result = Orchestrator().run(sources)

    assert result.analysis.status == "failed"
    assert result.validation_status == "not_run"


def test_orchestrator_handles_empty_sources():
    result = Orchestrator().run({})

    assert result.analysis.status == "no_supported_files"
    assert result.validation_status == "not_run"


def test_orchestrator_analyzes_repository_snapshot():
    snapshot = RepoSnapshot(
        files={
            "sample/app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "sample/requirements.txt": "fastapi>=0.100\n",
        }
    )

    result = Orchestrator().run_repository(snapshot, root_name="sample")

    assert result.analysis.status == "completed"
    assert result.analysis.parsed_files == 1
    assert result.repository_analysis is not None
    assert result.repository_analysis.project_name == "sample"
    assert "FastAPI" in result.repository_analysis.frameworks
    assert result.validation_status == "not_run"


def test_orchestrator_handles_repository_without_python_files():
    snapshot = RepoSnapshot(files={"sample/README.md": "Project documentation"})

    result = Orchestrator().run_repository(snapshot, root_name="sample")

    assert result.repository_analysis is not None
    assert result.repository_analysis.python_analysis.status == ("no_supported_files")
    assert result.validation_status == "not_run"


def test_orchestrator_generates_architecture_when_configured():
    snapshot = RepoSnapshot(
        files={
            "app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "requirements.txt": "fastapi\n",
        }
    )
    architecture_agent = ArchitectureAgent(StubArchitectureLLM())
    orchestrator = Orchestrator(architecture_agent=architecture_agent)

    result = orchestrator.run_repository(
        snapshot,
        root_name="sample",
        requirements="Deploy as a web API",
    )

    assert isinstance(result.architecture_proposal, ArchitectureProposal)
    assert result.architecture_proposal.project_name == "sample"
    assert result.architecture_proposal.components[0].name == "API"
    assert result.validation_status == "not_run"


def test_orchestrator_skips_architecture_when_not_configured():
    snapshot = RepoSnapshot(files={"app.py": "app = 1\n"})

    result = Orchestrator().run_repository(snapshot, root_name="sample")

    assert result.repository_analysis is not None
    assert result.architecture_proposal is None
    assert result.validation_status == "not_run"
