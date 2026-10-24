from __future__ import annotations

from uuid import UUID

from AI.application.ports.llm_provider import LLMRequest, LLMResponse, TokenUsage
from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import (
    AnalysisManifest,
    AnalysisReport,
    ComponentSpec,
    ComponentType,
    Evidence,
    LanguageStat,
    RepositoryRef,
    UserFact,
)
from AI.domain.shared.states import RunStatus


def make_repo() -> RepositoryRef:
    return RepositoryRef(owner="acme", name="api", commit_sha="abc123")


def make_report(
    repo: RepositoryRef | None = None,
    *,
    languages: bool = True,
    entry_points: bool = True,
    components: tuple[ComponentSpec, ...] | None = None,
) -> AnalysisReport:
    resolved_components: tuple[ComponentSpec, ...]
    if components is not None:
        resolved_components = components
    else:
        resolved_components = (
            ComponentSpec(
                name="api",
                root_dir=".",
                type=ComponentType.SERVER,
                language="Python" if languages else "",
                runtime_version="3.12",
                pkg_mgr="pip",
                start_cmd="uvicorn main:app --port 8000" if entry_points else None,
                port=8000,
                health_path="/health",
                evidence=(
                    Evidence(field="port", file="main.py", lines=(10, 12), snippet="port=8000"),
                    Evidence(
                        field="start_cmd",
                        file="Dockerfile",
                        lines=(5, 5),
                        snippet='CMD ["uvicorn", "main:app", "--port", "8000"]',
                    ),
                ),
                field_confidence={"port": 0.95, "start_cmd": 0.95},
            ),
        )

    return AnalysisManifest(
        repo=repo or make_repo(),
        components=resolved_components,
        languages=(LanguageStat("Python", 1200),) if languages else (),
        frameworks=("fastapi",),
        dependencies=(),
        entry_points=("main.py",) if entry_points else (),
        summary="A small FastAPI service.",
    )


class FakeAnalyzer:
    def __init__(
        self,
        report: AnalysisReport | None = None,
        error: Exception | None = None,
        reports_sequence: list[AnalysisReport] | None = None,
    ) -> None:
        self._report = report
        self._error = error
        self._sequence = list(reports_sequence) if reports_sequence else []
        self.calls: list[tuple[RepositoryRef, tuple[str, ...], tuple[UserFact, ...]]] = []

    async def analyze(
        self,
        repo: RepositoryRef,
        *,
        validation_feedback: tuple[str, ...] = (),
        user_facts: tuple[UserFact, ...] = (),
    ) -> AnalysisReport:
        self.calls.append((repo, validation_feedback, user_facts))
        if self._error is not None:
            raise self._error
        if self._sequence:
            return self._sequence.pop(0)
        return self._report or make_report(repo)


class FakeStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[RunStatus, str | None]] = []
        self.saved: list[tuple[UUID, AnalysisReport, tuple[Blocker, ...]]] = []

    async def set_status(
        self, run_id: UUID, status: RunStatus, error_code: str | None = None
    ) -> None:
        self.statuses.append((status, error_code))

    async def save_analysis(
        self, run_id: UUID, report: AnalysisReport, blockers: tuple[Blocker, ...]
    ) -> None:
        self.saved.append((run_id, report, blockers))


class FakeRepositoryReader:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files: dict[str, str] = files or {
            "Dockerfile": 'FROM python:3.12\nEXPOSE 8000\nCMD ["uvicorn", "main:app", "--port", "8000"]\n',
            "requirements.txt": "fastapi==0.115.0\nuvicorn==0.30.0\n",
            "main.py": 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef health(): return {"ok": True}\n# port 8000\n',
            ".env.example": "DATABASE_URL=postgres://user:secretpass@localhost:5432/db\nPORT=8000\n",
        }

    async def list_files(self, repo: RepositoryRef, access_token: str = "") -> tuple[str, ...]:
        return tuple(self.files.keys())

    async def read_file(self, repo: RepositoryRef, path: str, access_token: str = "") -> str:
        return self.files.get(path, "")


class FakeLLMProvider:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        text = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        return LLMResponse(
            text=text,
            model="fake-gemini",
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            finish_reason="stop",
        )
