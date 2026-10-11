from agents.code_analyzer import (
    CodeAnalyzerAgent,
    RepositoryAnalysis,
)
from workflows.repository import RepoSnapshot


def test_existing_run_interface_remains_compatible():
    report = CodeAnalyzerAgent().run({"app.py": "def main():\n    pass\n"})

    assert report.parsed_files == 1
    assert report.files[0].path == "app.py"


def test_agent_analyzes_repository_snapshot():
    snapshot = RepoSnapshot(
        files={
            "sample/app.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "sample/requirements.txt": "fastapi>=0.100\n",
        }
    )

    report = CodeAnalyzerAgent().analyze_repository(
        snapshot,
        root_name="sample",
    )

    assert isinstance(report, RepositoryAnalysis)
    assert report.project_name == "sample"
    assert "FastAPI" in report.frameworks
    assert "fastapi" in report.dependencies
    assert report.python_analysis.parsed_files == 1
