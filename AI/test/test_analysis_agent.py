import asyncio
import json

from AI.agents.analysis.agent import LangGraphAnalysisAgent
from AI.application.analysis.pdf_report import (
    MAX_USER_REPORT_CHARS,
    ensure_complete_summary,
    generate_user_pdf_report,
)
from AI.application.analysis.redactor import format_with_line_numbers, redact_secrets
from AI.domain.analysis.models import FactSource, UserFact
from AI.test.fakes import FakeLLMProvider, FakeRepositoryReader, make_repo, make_report


def test_redactor_strips_env_values_and_secrets():
    env_raw = "DATABASE_URL=postgres://admin:supersecret@db.internal:5432/prod\nAPI_KEY='sk-1234567890abcdef'\nEMPTY_VAR=\n"
    redacted_env = redact_secrets(env_raw, path=".env.example")
    assert "supersecret" not in redacted_env
    assert "sk-1234567890abcdef" not in redacted_env
    assert "DATABASE_URL=<REDACTED>" in redacted_env
    assert "API_KEY=<REDACTED>" in redacted_env
    assert "EMPTY_VAR=" in redacted_env

    code_raw = 'const key = "AKIAIOSFODNN7EXAMPLE";\nconst db = "postgres://u:mysecret@host/db";'
    numbered = format_with_line_numbers(code_raw, path="config.ts")
    assert "AKIAIOSFODNN7EXAMPLE" not in numbered
    assert "mysecret" not in numbered
    assert "1: " in numbered
    assert "2: " in numbered


def test_langgraph_analysis_agent_executes_react_loop_and_builds_manifest():
    step_1_react = json.dumps(
        {
            "thought": "Need to read main.py to check the health endpoint and port.",
            "actions": [
                {"tool": "read_repo_file", "argument": "main.py", "reason": "Check health route"},
            ],
        }
    )
    step_2_react = json.dumps(
        {
            "thought": "All needed files have been read.",
            "actions": [{"tool": "finish", "argument": "", "reason": "Ready to synthesize"}],
        }
    )
    final_manifest_json = json.dumps(
        {
            "components": [
                {
                    "name": "api",
                    "root_dir": ".",
                    "type": "server",
                    "language": "Python",
                    "runtime_version": "3.12",
                    "pkg_mgr": "pip",
                    "build_cmd": None,
                    "start_cmd": "uvicorn main:app --port 8000",
                    "output_dir": None,
                    "port": 8000,
                    "health_path": "/health",
                    "env_vars": [
                        {
                            "name": "DATABASE_URL",
                            "required": True,
                            "scope": "runtime",
                            "is_secret": True,
                        }
                    ],
                    "dependencies": [
                        {
                            "name": "postgres",
                            "kind": "database",
                            "required": True,
                            "evidence_file": ".env.example",
                        }
                    ],
                    "evidence": [
                        {
                            "field": "start_cmd",
                            "file": "Dockerfile",
                            "lines": [3, 3],
                            "snippet": 'CMD ["uvicorn", "main:app", "--port", "8000"]',
                        },
                        {
                            "field": "port",
                            "file": "Dockerfile",
                            "lines": [2, 2],
                            "snippet": "EXPOSE 8000",
                        },
                    ],
                    "field_confidence": {"start_cmd": 0.95, "port": 0.95, "health_path": 0.9},
                }
            ],
            "relationships": [],
            "topology": "single_service",
            "topology_confidence": 0.95,
            "open_questions": [],
            "languages": [{"name": "Python", "bytes_of_code": 1500}],
            "frameworks": ["fastapi"],
            "dependencies": [{"name": "fastapi", "ecosystem": "pip", "version": "0.115.0"}],
            "entry_points": ["main.py"],
            "summary": "FastAPI service running on port 8000.",
        }
    )

    llm = FakeLLMProvider([step_1_react, step_2_react, final_manifest_json])
    reader = FakeRepositoryReader()
    agent = LangGraphAnalysisAgent(llm=llm, reader=reader, max_tool_steps=2)

    user_facts = (
        UserFact(component="api", field_path="api.port", value="9000", source=FactSource.USER),
    )
    manifest = asyncio.run(agent.analyze(make_repo(), user_facts=user_facts))

    assert manifest.repo == make_repo()
    assert len(manifest.components) == 1
    comp = manifest.components[0]
    assert comp.name == "api"
    # User fact overrides LLM-inferred port (9000 > 8000) with confidence 1.0
    assert comp.port == 9000
    assert comp.confidence_for("port") == 1.0
    assert comp.env_vars[0].name == "DATABASE_URL"
    assert comp.env_vars[0].is_secret is True
    # Ensure secret values from .env.example never entered any LLM prompt
    for req in llm.requests:
        assert "secretpass" not in req.user


def test_pdf_report_generation_and_250_char_complete_sentence(tmp_path):
    long_text = (
        "This is a FastAPI web service running on port 8000 with a /health check endpoint. "
        "It uses Pydantic Settings for environment configuration and requires an API_KEY secret at runtime. "
        "This extra third sentence pushes the total length well beyond two hundred and fifty characters so we can verify clean sentence boundary truncation."
    )
    bounded = ensure_complete_summary(long_text)
    assert len(bounded) <= MAX_USER_REPORT_CHARS
    assert bounded.endswith(".")

    pdf_file = tmp_path / "user_report.pdf"
    out_path = generate_user_pdf_report(make_report(), pdf_file)
    assert out_path.exists()
    assert out_path.stat().st_size > 500
