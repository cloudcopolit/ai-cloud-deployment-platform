"""Golden-repository tests for the deterministic Analysis Agent (10 §5, A2.1-A2.8)."""

from __future__ import annotations

import pytest
from cloudpilot_ai import analyze_repository, run_analysis
from cloudpilot_ai.analysis.secrets import redact
from cloudpilot_ai.contracts import AnalysisReport, JobStatus
from cloudpilot_ai.errors import Budget
from cloudpilot_ai.trace import Tracer

from tests import fixture_repos as repos
from tests.fakes import MemoryRepo, RecordingSink, request


def analyze(files: dict[str, str], **request_overrides) -> AnalysisReport:
    sink = RecordingSink()
    with Tracer(sink).run("ANALYSIS", {}) as run:
        return analyze_repository(
            request(**request_overrides),
            repository=MemoryRepo(files),
            llm=None,
            run=run,
            budget=Budget(seconds=30),
        )


def service(report: AnalysisReport, name: str | None = None):
    if name is None:
        assert len(report.services) == 1, [s.name for s in report.services]
        return report.services[0]
    return next(s for s in report.services if s.name == name)


def codes(findings) -> set[str]:
    return {f.code for f in findings}


def test_fastapi_postgres() -> None:
    report = analyze(repos.FASTAPI_POSTGRES)
    svc = service(report)
    assert (svc.language, svc.framework, svc.port, svc.health_endpoint) == (
        "python",
        "FastAPI",
        8000,
        "/health",
    )
    assert svc.has_dockerfile
    assert svc.service_type.value == "api"
    assert {d.engine for d in report.data_stores} == {"postgresql"}
    assert {e.name for e in report.env_vars} >= {"DATABASE_URL", "JWT_SECRET"}
    assert report.is_deployable
    assert report.recommendation is not None
    assert report.recommendation.method == "container"
    assert report.recommendation.automated_by_cloudpilot is True
    assert {c.kind for c in report.config_files} >= {"dockerfile", "env_example", "ci"}
    assert all(e.content_sha256 and len(e.content_sha256) == 64 for e in svc.evidence)


def test_express_mongo_without_dockerfile() -> None:
    report = analyze(repos.EXPRESS_MONGO)
    svc = service(report)
    assert (svc.framework, svc.port, svc.health_endpoint, svc.name) == (
        "Express",
        3000,
        "/healthz",
        "orders-api",
    )
    assert {d.engine for d in report.data_stores} == {"mongodb"}
    assert {"NO_DOCKERFILE", "NO_LOCKFILE"} <= codes(report.warnings)
    assert "MONGO_URL" in {e.name for e in report.env_vars}
    assert report.recommendation is not None
    assert report.recommendation.automated_by_cloudpilot is False  # needs Dockerfile + MongoDB


def test_static_site_is_automatable_without_a_build() -> None:
    report = analyze(repos.STATIC_SITE)
    svc = service(report)
    assert svc.metadata["static_site"] is True
    assert report.recommendation is not None
    assert report.recommendation.method == "static_site"
    assert report.recommendation.automated_by_cloudpilot is True
    assert "NO_HEALTH_ENDPOINT" not in codes(report.warnings)
    assert report.is_deployable


def test_nextjs_is_a_web_server_not_a_static_site() -> None:
    report = analyze(repos.NEXTJS)
    svc = service(report)
    assert (svc.framework, svc.service_type.value, svc.port, svc.language) == (
        "Next.js",
        "web",
        3000,
        "typescript",
    )
    assert svc.health_endpoint is None or svc.health_endpoint.endswith("health")
    assert report.recommendation is not None
    assert report.recommendation.method == "container"


def test_spring_boot_reads_server_port_and_actuator() -> None:
    report = analyze(repos.SPRING_BOOT)
    svc = service(report)
    assert (svc.language, svc.framework, svc.port, svc.health_endpoint) == (
        "java",
        "Spring Boot",
        8081,
        "/actuator/health",
    )
    framework = next(f for f in report.frameworks if f.name == "Spring Boot")
    assert framework.version == "3.3.4"
    assert {d.engine for d in report.data_stores} == {"postgresql"}
    assert "DATABASE_URL" in {e.name for e in report.env_vars}


def test_go_gin() -> None:
    report = analyze(repos.GO_GIN)
    svc = service(report)
    assert (svc.language, svc.framework, svc.port, svc.health_endpoint) == (
        "go",
        "Gin",
        8080,
        "/ping",
    )
    assert {d.engine for d in report.data_stores} == {"postgresql"}


def test_monorepo_with_kafka_is_analyzed_honestly() -> None:
    report = analyze(repos.MONOREPO_KAFKA)
    names = {s.name: s for s in report.services}
    assert set(names) == {"api", "web"}
    assert (names["api"].path, names["api"].port, names["api"].framework) == (
        "api",
        8000,
        "FastAPI",
    )
    assert (names["web"].path, names["web"].port, names["web"].framework) == (
        "web",
        3000,
        "Next.js",
    )
    assert {d.engine for d in report.data_stores} == {"kafka", "postgresql", "redis"}
    assert {"KAFKA_BROKERS", "REDIS_URL"} <= {e.name for e in report.env_vars}
    rec = report.recommendation
    assert rec is not None
    assert rec.method == "container"
    assert rec.automated_by_cloudpilot is False
    assert "Kafka" in rec.reasoning
    assert "Redis" in rec.reasoning
    assert report.is_deployable  # an honest plan, not a block
    assert "Monorepo with 2 services" in report.summary


def test_no_start_command_is_blocked() -> None:
    report = analyze(repos.NO_START_COMMAND)
    assert report.services == []
    assert "NO_DEPLOYABLE_SERVICE" in codes(report.blockers)
    assert not report.is_deployable
    assert report.recommendation is not None
    assert report.recommendation.method == "unsupported"


def test_sqlite_only_blocks_until_answered() -> None:
    report = analyze(repos.SQLITE_ONLY)
    assert "REQUIRES_LOCAL_ONLY_RESOURCE" in codes(report.blockers)
    assert [m.key for m in report.missing_info] == ["datastore:sqlite"]
    assert not report.is_deployable

    rerun = analyze(repos.SQLITE_ONLY, user_answers={"datastore:sqlite": "postgresql"})
    assert rerun.blockers == []
    assert "SQLITE_PRIMARY_DATABASE" in codes(rerun.warnings)
    assert rerun.is_deployable


def test_missing_port_becomes_a_question_and_an_answer_unblocks() -> None:
    files = {
        "requirements.txt": "flask==3.0.3\n",
        "app.py": "from flask import Flask\napp = Flask(__name__)\n",
        "Dockerfile": 'FROM python:3.12-slim\nCMD ["python", "app.py"]\n',
    }
    report = analyze(files)
    svc = service(report)
    assert svc.port == 5000  # framework default, low confidence
    assert svc.metadata["port_confidence"] == 0.4

    no_default = {"Dockerfile": "FROM node:24\nCMD node x.js\n", "x.js": "require('http')"}
    blocked = analyze(no_default)
    assert blocked.missing_info
    assert blocked.missing_info[0].key.startswith("port:")
    answered = analyze(no_default, user_answers={blocked.missing_info[0].key: "9000"})
    assert service(answered).port == 9000
    assert service(answered).metadata["port_source"] == "answered by the user"


def test_committed_secret_is_reported_by_path_and_kind_only() -> None:
    report = analyze(repos.SECRET_COMMITTED)
    secrets = [f for f in report.blockers if f.code == "SECRET_COMMITTED"]
    assert {f.evidence[0].file_path for f in secrets} == {"app/settings.py", ".env"}
    assert any("AWS access key id" in f.message for f in secrets)
    dumped = report.model_dump_json()
    assert "AKIAIOSFODNN7EXAMPLE" not in dumped
    assert "wJalrXUtnFEMI" not in dumped
    assert "ENV_FILE_COMMITTED" in codes(report.warnings)
    assert not report.is_deployable


def test_prompt_injection_text_changes_nothing() -> None:
    clean = analyze(repos.FASTAPI_POSTGRES)
    injected = analyze(repos.PROMPT_INJECTION)
    assert [s.model_dump() for s in injected.services] == [s.model_dump() for s in clean.services]
    assert injected.blockers == clean.blockers
    assert "pwned" not in injected.model_dump_json()
    assert injected.recommendation == clean.recommendation


def test_unsupported_stack_is_reported_not_guessed() -> None:
    report = analyze(repos.UNSUPPORTED_ELIXIR)
    assert [u.name for u in report.unsupported] == ["elixir"]
    assert not report.is_deployable


def test_install_hooks_are_only_read_never_run() -> None:
    repo = MemoryRepo(repos.MALICIOUS_INSTALL_HOOKS)
    sink = RecordingSink()
    with Tracer(sink).run("ANALYSIS", {}) as run:
        report = analyze_repository(
            request(), repository=repo, llm=None, run=run, budget=Budget(seconds=30)
        )
    assert service(report).port == 8080
    # the only way content entered the process is read_file; nothing was executed
    assert set(repo.reads) <= set(repos.MALICIOUS_INSTALL_HOOKS)


def test_limits_mark_the_report_truncated() -> None:
    big = {f"src/m{i}.py": "x = 1\n" for i in range(50)} | repos.FASTAPI_POSTGRES
    report = analyze(big, limits_max_files=5)
    assert report.meta.truncated is True
    assert report.meta.files_scanned <= 5
    assert "ANALYSIS_TRUNCATED" in codes(report.warnings)


def test_generated_and_binary_files_are_never_read() -> None:
    files = repos.EXPRESS_MONGO | {
        "node_modules/express/index.js": "x",
        "dist/bundle.js": "x",
        "logo.png": "x",
    }
    repo = MemoryRepo(files)
    with Tracer(RecordingSink()).run("ANALYSIS", {}) as run:
        analyze_repository(request(), repository=repo, llm=None, run=run, budget=Budget(seconds=30))
    assert not any(
        p.startswith(("node_modules/", "dist/")) or p.endswith(".png") for p in repo.reads
    )


def test_every_step_is_traced_for_the_live_view() -> None:
    sink = RecordingSink()
    outcome = run_analysis(
        request(),
        repository=MemoryRepo(repos.FASTAPI_POSTGRES),
        sink=sink,
        analysis_agent=analyze_repository,
    )
    assert outcome.status is JobStatus.SUCCESS
    tasks = [e.args["type"] for e in sink.events if e.kind == "task_started"]
    assert tasks == [
        "read_repository",
        "detect_languages_and_frameworks",
        "detect_containers_and_config",
        "detect_env_ports_health",
        "scan_for_secrets",
        "resolve_ambiguity_with_llm",
        "assemble_report",
    ]
    skipped = [
        e.args for e in sink.events if e.kind == "task_finished" and e.args["status"] == "SKIPPED"
    ]
    assert len(skipped) == 1  # the LLM step, honestly marked as skipped


@pytest.mark.parametrize(
    ("text", "leak"),
    [
        ("key = AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
        ("DB_PASSWORD=s3cr3tvalue123", "s3cr3tvalue123"),
        ("token: ghp_" + "a" * 36, "ghp_" + "a" * 36),
        ("-----BEGIN RSA PRIVATE KEY-----", "BEGIN RSA PRIVATE KEY"),
    ],
)
def test_redact_removes_secrets_before_prompts(text: str, leak: str) -> None:
    assert leak not in redact(text)


def test_redact_keeps_placeholders_and_names() -> None:
    assert redact("DATABASE_URL=${DATABASE_URL}\nPASSWORD=changeme") == (
        "DATABASE_URL=${DATABASE_URL}\nPASSWORD=changeme"
    )
