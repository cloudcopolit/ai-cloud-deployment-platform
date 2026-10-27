"""Communication Module (06 §6): routes the orchestrator's requests to agents and ports,
enforcing per-stage timeouts and retries and normalizing every failure to an ErrorInfo.
It contains no business or AI logic."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar
from uuid import UUID

from cloudpilot_ai.contracts import (
    AnalysisReport,
    AnalysisRequest,
    ArchitecturePlan,
    ErrorCode,
    ErrorInfo,
    Stage,
)
from cloudpilot_ai.errors import AgentError, Budget
from cloudpilot_ai.ports import InfraDiscovery, LLMGateway, RepositoryGateway
from cloudpilot_ai.trace import RunScope, Tracer

T = TypeVar("T")


class AnalysisAgent(Protocol):
    def __call__(
        self,
        request: AnalysisRequest,
        *,
        repository: RepositoryGateway,
        llm: LLMGateway | None,
        run: RunScope,
        budget: Budget,
    ) -> AnalysisReport: ...


class ArchitectureAgent(Protocol):
    def __call__(
        self,
        report: AnalysisReport,
        *,
        source_analysis_id: UUID,
        region: str,
        llm: LLMGateway | None,
        run: RunScope,
        budget: Budget,
    ) -> ArchitecturePlan: ...


@dataclass(frozen=True)
class StagePolicy:
    timeout_s: float
    retries: int = 0


@dataclass(frozen=True)
class Policies:
    """Starting points from 06 §3.5."""

    analysis: StagePolicy = field(default_factory=lambda: StagePolicy(timeout_s=180, retries=1))
    discovery: StagePolicy = field(default_factory=lambda: StagePolicy(timeout_s=60, retries=0))
    architecture: StagePolicy = field(default_factory=lambda: StagePolicy(timeout_s=180, retries=1))


class CommunicationModule:
    def __init__(
        self,
        *,
        tracer: Tracer,
        budget: Budget,
        repository: RepositoryGateway,
        analysis_agent: AnalysisAgent,
        architecture_agent: ArchitectureAgent | None = None,
        llm: LLMGateway | None = None,
        infra: InfraDiscovery | None = None,
        policies: Policies | None = None,
    ) -> None:
        self.tracer = tracer
        self.budget = budget
        self.repository = repository
        self.analysis_agent = analysis_agent
        self.architecture_agent = architecture_agent
        self.llm = llm
        self.infra = infra
        self.policies = policies or Policies()

    @property
    def has_architect(self) -> bool:
        return self.architecture_agent is not None

    # ───────────────────────── routing ─────────────────────────
    def analyze(self, request: AnalysisRequest) -> AnalysisReport:
        def call(run: RunScope) -> AnalysisReport:
            return self.analysis_agent(
                request, repository=self.repository, llm=self.llm, run=run, budget=self.budget
            )

        summary = {
            "repository": f"{request.repository.owner}/{request.repository.name}",
            "commit_sha": request.repository.commit_sha,
            "branch": request.repository.branch,
            "answers": sorted(request.user_answers),  # keys only
        }
        return self._with_retries("ANALYSIS", summary, Stage.ANALYZE, self.policies.analysis, call)

    def architect(
        self, report: AnalysisReport, *, source_analysis_id: UUID, region: str
    ) -> ArchitecturePlan:
        agent = self.architecture_agent
        if agent is None:  # pragma: no cover - the graph does not route here without one
            raise AgentError.of(ErrorCode.INTERNAL_ERROR, "No architecture agent configured.")

        def call(run: RunScope) -> ArchitecturePlan:
            return agent(
                report,
                source_analysis_id=source_analysis_id,
                region=region,
                llm=self.llm,
                run=run,
                budget=self.budget,
            )

        summary = {"services": len(report.services), "region": region}
        return self._with_retries(
            "ARCHITECTURE", summary, Stage.ARCHITECT, self.policies.architecture, call
        )

    def discover(self) -> tuple[dict[str, Any] | None, ErrorInfo | None]:
        """Optional, read-only. Failures are warnings, never fatal (06 §3.2)."""
        if self.infra is None:
            return None, None
        infra = self.infra
        try:
            result = self._timed(
                infra.discover, self.policies.discovery, Stage.DISCOVER_INFRA, abort=False
            )
            return result, None
        except AgentError as exc:
            return None, ErrorInfo(
                code=ErrorCode.AWS_DISCOVERY_FAILED,
                message="AWS discovery failed; the analysis continues without it.",
                stage=Stage.DISCOVER_INFRA,
                details={"cause": exc.info.code.value},
            )

    # ───────────────────────── mechanics ─────────────────────────
    def _with_retries(
        self,
        agent: str,
        summary: dict[str, Any],
        stage: Stage,
        policy: StagePolicy,
        call: Callable[[RunScope], T],
    ) -> T:
        attempt = 0
        while True:
            attempt += 1
            self.budget.check(stage)
            try:
                with self.tracer.run(agent, {**summary, "attempt": attempt}) as run:  # type: ignore[arg-type]
                    return self._timed(lambda: call(run), policy, stage)
            except AgentError as exc:
                if not exc.info.retryable or attempt > policy.retries:
                    raise

    def _timed(
        self, fn: Callable[[], T], policy: StagePolicy, stage: Stage, *, abort: bool = True
    ) -> T:
        timeout = min(policy.timeout_s, self.budget.remaining())
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            error = AgentError.of(
                ErrorCode.STAGE_TIMEOUT,
                f"{stage.value.lower().replace('_', ' ')} took longer than {int(timeout)} s.",
                stage=stage,
            )
            if abort:  # the abandoned agent thread stops at its next budget check
                self.budget.abort(error)
            raise error from None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
