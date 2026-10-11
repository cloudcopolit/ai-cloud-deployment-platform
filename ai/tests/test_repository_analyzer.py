from agents.code_analyzer.repository_analyzer import analyze_repository
from workflows.repository import RepoSnapshot


def test_analyzes_project_structure_and_python_entry_points():
    snapshot = RepoSnapshot(
        files={
            "demo/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "demo/requirements.txt": "fastapi>=0.100\nrequests==2.31.0\n",
            "demo/Dockerfile": "FROM python:3.12-slim\n",
        }
    )

    report = analyze_repository(snapshot, root_name="demo")

    assert report.project_name == "demo"
    assert report.languages == ("Python",)
    assert "demo/" in report.project_structure
    assert "demo/main.py" in report.entry_points
    assert "demo/Dockerfile" in report.config_files
    assert report.dependencies == ("fastapi", "requests")
    assert "FastAPI" in report.frameworks
    assert report.python_analysis.parsed_files == 1


def test_reads_pyproject_metadata_and_dependencies():
    snapshot = RepoSnapshot(
        files={
            "pyproject.toml": (
                "[project]\n"
                'name = "sample-app"\n'
                'dependencies = ["flask>=3.0", "pydantic"]\n'
            ),
            "app.py": "from flask import Flask\n",
        }
    )

    report = analyze_repository(snapshot)

    assert report.project_name == "sample-app"
    assert report.dependencies == ("flask", "pydantic")
    assert "Flask" in report.frameworks


def test_malformed_manifest_does_not_crash_analysis():
    snapshot = RepoSnapshot(
        files={
            "pyproject.toml": "not valid TOML = [",
            "app.py": "print('hello')\n",
        }
    )

    report = analyze_repository(snapshot, root_name="fallback")

    assert report.project_name == "fallback"
    assert report.python_analysis.parsed_files == 1
    assert report.metadata_errors


def test_does_not_execute_uploaded_python():
    snapshot = RepoSnapshot(
        files={"app.py": "raise RuntimeError('must not execute')\n"}
    )

    report = analyze_repository(snapshot)

    assert report.python_analysis.parsed_files == 1
    assert report.python_analysis.files[0].status == "parsed"
