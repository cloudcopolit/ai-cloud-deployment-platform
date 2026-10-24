from __future__ import annotations

import json
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, ValidationError

from AI.agents.analysis.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    build_synthesis_prompt,
)
from AI.application.ports.llm_provider import LLMProvider, LLMRequest
from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import (
    AnalysisManifest,
    ComponentRelationship,
    ComponentSpec,
    ComponentType,
    Dependency,
    EnvScope,
    EnvVarSpec,
    Evidence,
    LanguageStat,
    OpenQuestion,
    RepositoryRef,
    ServiceDependency,
    UserFact,
)
from AI.domain.shared.errors import AnalysisFailedError, InvalidModelOutputError
from AI.infrastructure.mcp.servers.repository_tools import (
    RepositoryToolset,
    is_signal_file,
)
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# Pydantic Schemas for LLM Tool Selection & Structured Report Output
# ---------------------------------------------------------------------------


class ToolCallSpec(BaseModel):
    tool: Literal["list_repo_files", "read_repo_file", "search_repo_files", "finish"]
    argument: str = Field(
        default="",
        description="File path for read_repo_file, search query for search_repo_files, or empty for list_repo_files/finish.",
    )
    reason: str = Field(default="", description="Brief reason for this action.")


class ReActStepOut(BaseModel):
    thought: str
    actions: list[ToolCallSpec] = Field(default_factory=list)


class EvidenceOut(BaseModel):
    field: str
    file: str
    lines: list[int] | None = Field(
        default=None, description="[start_line, end_line] (1-based inclusive)"
    )
    snippet: str = ""


class EnvVarSpecOut(BaseModel):
    name: str
    required: bool = True
    scope: Literal["build", "runtime"] = "runtime"
    is_secret: bool = False


class ServiceDependencyOut(BaseModel):
    name: str
    kind: str = "service"
    required: bool = True
    evidence_file: str | None = None


class ComponentSpecOut(BaseModel):
    name: str
    root_dir: str = "."
    type: Literal["static", "server", "worker"] = "server"
    language: str
    runtime_version: str | None = None
    pkg_mgr: str | None = None
    build_cmd: str | None = None
    start_cmd: str | None = None
    output_dir: str | None = None
    port: int | None = None
    health_path: str | None = None
    env_vars: list[EnvVarSpecOut] = Field(default_factory=list)
    dependencies: list[ServiceDependencyOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)


class ComponentRelationshipOut(BaseModel):
    source_component: str
    target_component: str
    kind: str = "http_api"
    via_env_var: str | None = None
    evidence: EvidenceOut | None = None


class OpenQuestionOut(BaseModel):
    component: str
    field_path: str
    question: str
    reason: str = ""


class LanguageStatOut(BaseModel):
    name: str
    bytes_of_code: int = 0


class DependencyOut(BaseModel):
    name: str
    ecosystem: str
    version: str | None = None


class ManifestOut(BaseModel):
    components: list[ComponentSpecOut] = Field(default_factory=list)
    relationships: list[ComponentRelationshipOut] = Field(default_factory=list)
    topology: str = "single_service"
    topology_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    open_questions: list[OpenQuestionOut] = Field(default_factory=list)
    languages: list[LanguageStatOut] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    dependencies: list[DependencyOut] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    summary: str = Field(
        default="",
        max_length=250,
        description="Complete, self-contained executive summary of the repository for the user PDF report. Must be <= 250 characters and end with a complete sentence.",
    )


# ---------------------------------------------------------------------------
# Internal LangGraph State for the ReAct Analysis Agent Subgraph
# ---------------------------------------------------------------------------


def _append_strings(left: list[str], right: list[str]) -> list[str]:
    return [*left, *right]


class AnalysisAgentState(TypedDict, total=False):
    repo: RepositoryRef
    validation_feedback: tuple[str, ...]
    user_facts: tuple[UserFact, ...]
    observations: Annotated[list[str], _append_strings]
    pending_actions: list[ToolCallSpec]
    step_count: int
    done_exploring: bool
    manifest: AnalysisManifest


# ---------------------------------------------------------------------------
# Conversion Helpers (Pydantic -> Immutable Domain Entities)
# ---------------------------------------------------------------------------


def _to_domain_evidence(ev: EvidenceOut) -> Evidence:
    lines: tuple[int, int] | None = None
    if ev.lines and len(ev.lines) >= 2:
        start = max(1, int(ev.lines[0]))
        end = max(start, int(ev.lines[1]))
        lines = (start, end)
    elif ev.lines and len(ev.lines) == 1:
        line_no = max(1, int(ev.lines[0]))
        lines = (line_no, line_no)
    return Evidence(field=ev.field, file=ev.file, lines=lines, snippet=ev.snippet)


def _to_domain_manifest(
    repo: RepositoryRef,
    out: ManifestOut,
    *,
    user_facts: tuple[UserFact, ...] = (),
) -> AnalysisManifest:
    # Build lookup of user facts so user ground truth always wins (user > scanner > llm)
    fact_map: dict[tuple[str, str], str] = {
        (f.component, f.field_path.split(".")[-1]): f.value for f in user_facts
    }

    components: list[ComponentSpec] = []
    for comp in out.components:
        port = comp.port
        start_cmd = comp.start_cmd
        build_cmd = comp.build_cmd
        health_path = comp.health_path
        confidence = dict(comp.field_confidence)

        if (comp.name, "port") in fact_map:
            try:
                port = int(fact_map[(comp.name, "port")])
                confidence["port"] = 1.0
            except ValueError:
                pass
        if (comp.name, "start_cmd") in fact_map:
            start_cmd = fact_map[(comp.name, "start_cmd")]
            confidence["start_cmd"] = 1.0
        if (comp.name, "build_cmd") in fact_map:
            build_cmd = fact_map[(comp.name, "build_cmd")]
            confidence["build_cmd"] = 1.0
        if (comp.name, "health_path") in fact_map:
            health_path = fact_map[(comp.name, "health_path")]
            confidence["health_path"] = 1.0

        env_vars = tuple(
            EnvVarSpec(
                name=e.name.split("=")[0].strip(),
                required=e.required,
                scope=EnvScope(e.scope),
                is_secret=e.is_secret,
            )
            for e in comp.env_vars
            if e.name.strip()
        )
        deps = tuple(
            ServiceDependency(
                name=d.name,
                kind=d.kind,
                required=d.required,
                evidence_file=d.evidence_file,
            )
            for d in comp.dependencies
        )
        evidences = tuple(_to_domain_evidence(ev) for ev in comp.evidence if ev.file)

        components.append(
            ComponentSpec(
                name=comp.name,
                root_dir=comp.root_dir,
                type=ComponentType(comp.type),
                language=comp.language,
                runtime_version=comp.runtime_version,
                pkg_mgr=comp.pkg_mgr,
                build_cmd=build_cmd,
                start_cmd=start_cmd,
                output_dir=comp.output_dir,
                port=port,
                health_path=health_path,
                env_vars=env_vars,
                dependencies=deps,
                evidence=evidences,
                field_confidence=confidence,
            )
        )

    relationships = tuple(
        ComponentRelationship(
            source_component=r.source_component,
            target_component=r.target_component,
            kind=r.kind,
            via_env_var=r.via_env_var,
            evidence=_to_domain_evidence(r.evidence) if r.evidence and r.evidence.file else None,
        )
        for r in out.relationships
    )

    resolved_keys = {(f.component, f.field_path) for f in user_facts} | {
        (f.component, f"{f.component}.{f.field_path.split('.')[-1]}") for f in user_facts
    }
    open_questions = tuple(
        OpenQuestion(
            component=q.component,
            field_path=q.field_path,
            question=q.question,
            reason=q.reason,
        )
        for q in out.open_questions
        if (q.component, q.field_path) not in resolved_keys
    )

    languages = tuple(
        LanguageStat(name=lang.name, bytes_of_code=lang.bytes_of_code)
        for lang in out.languages
    )
    if not languages and components:
        seen_langs: dict[str, int] = {}
        for c in components:
            if c.language:
                seen_langs[c.language] = seen_langs.get(c.language, 0) + 1000
        languages = tuple(LanguageStat(name=k, bytes_of_code=v) for k, v in seen_langs.items())

    entry_points = list(out.entry_points)
    if not entry_points:
        for c in components:
            if c.start_cmd:
                entry_points.append(c.start_cmd)
            elif c.build_cmd:
                entry_points.append(c.build_cmd)

    return AnalysisManifest(
        repo=repo,
        components=tuple(components),
        relationships=relationships,
        topology=out.topology,
        topology_confidence=out.topology_confidence,
        open_questions=open_questions,
        languages=languages,
        frameworks=tuple(out.frameworks),
        dependencies=tuple(
            Dependency(name=d.name, ecosystem=d.ecosystem, version=d.version)
            for d in out.dependencies
        ),
        entry_points=tuple(entry_points),
        summary=out.summary,
    )


# ---------------------------------------------------------------------------
# LangGraph ReAct Analysis Agent Implementation
# ---------------------------------------------------------------------------


class LangGraphAnalysisAgent:
    """LangGraph ReAct / tool-calling agent that inspects a repository and produces an AnalysisManifest."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        reader: RepositoryReader,
        access_token: str = "",
        max_tool_steps: int = 3,
        max_parse_retries: int = 2,
    ) -> None:
        self._llm = llm
        self._reader = reader
        self._access_token = access_token
        self._max_tool_steps = max_tool_steps
        self._max_parse_retries = max_parse_retries

    def build_graph(self, toolset: RepositoryToolset) -> Any:
        graph = StateGraph(AnalysisAgentState)

        async def bootstrap_tools_node(state: AnalysisAgentState) -> dict[str, Any]:
            """Initial deterministic pass: list repository files and read top signal files."""
            tree_summary = await toolset.list_repo_files()
            files = await self._reader.list_files(state["repo"], self._access_token)
            signal_files = [f for f in files if is_signal_file(f)][:6]
            observations = [tree_summary]
            for sf in signal_files:
                observations.append(await toolset.read_repo_file(sf))
            return {
                "observations": observations,
                "step_count": 0,
                "done_exploring": self._max_tool_steps <= 0 or not files,
            }

        async def reason_node(state: AnalysisAgentState) -> dict[str, Any]:
            """ReAct reasoning step: decide if additional files/searches are needed before synthesis."""
            step = state.get("step_count", 0)
            if step >= self._max_tool_steps or state.get("done_exploring"):
                return {"done_exploring": True, "pending_actions": []}

            obs_preview = "\n\n".join(state.get("observations", []))
            planner_prompt = (
                f"Repository: {state['repo'].full_name}@{state['repo'].commit_sha}\n"
                f"Current observations:\n{obs_preview}\n\n"
                "Do you need to read any additional entry-point files or search for ports/routes "
                "before generating the final AnalysisManifest? "
                "Respond with JSON matching ReActStepOut: "
                '{"thought": "...", "actions": [{"tool": "read_repo_file"|"search_repo_files"|"finish", "argument": "..."}]}'
            )
            response = await self._llm.complete(
                LLMRequest(
                    system=ANALYSIS_SYSTEM_PROMPT,
                    user=planner_prompt,
                    expect_json=True,
                    temperature=0.0,
                )
            )
            try:
                parsed = ReActStepOut.model_validate_json(response.text)
            except ValidationError:
                # If the LLM already returned the final ManifestOut or decided to stop, proceed to synthesize.
                return {"done_exploring": True, "pending_actions": []}

            non_finish = [a for a in parsed.actions if a.tool != "finish" and a.argument.strip()]
            if not non_finish:
                return {"done_exploring": True, "pending_actions": []}
            return {
                "pending_actions": non_finish[:4],
                "step_count": step + 1,
                "done_exploring": False,
            }

        async def act_tools_node(state: AnalysisAgentState) -> dict[str, Any]:
            """Execute the tool calls requested by the ReAct reasoning step."""
            actions = state.get("pending_actions", [])
            new_obs: list[str] = []
            for action in actions:
                if action.tool == "list_repo_files":
                    new_obs.append(await toolset.list_repo_files())
                elif action.tool == "read_repo_file":
                    new_obs.append(await toolset.read_repo_file(action.argument))
                elif action.tool == "search_repo_files":
                    new_obs.append(await toolset.search_repo_files(action.argument))
            return {"observations": new_obs, "pending_actions": []}

        async def synthesize_node(state: AnalysisAgentState) -> dict[str, Any]:
            """Synthesize all tool observations into a verified AnalysisManifest JSON."""
            repo = state["repo"]
            feedback = state.get("validation_feedback", ())
            user_facts = state.get("user_facts", ())
            observations = state.get("observations", [])

            schema_json = json.dumps(ManifestOut.model_json_schema(), indent=2)
            base_prompt = (
                build_synthesis_prompt(
                    repo,
                    observations,
                    validation_feedback=feedback,
                    user_facts=user_facts,
                )
                + f"\n\n### Expected JSON Schema\n```json\n{schema_json}\n```"
            )

            last_error: str | None = None
            for attempt in range(self._max_parse_retries + 1):
                prompt = (
                    base_prompt
                    if last_error is None
                    else f"{base_prompt}\n\nPrevious JSON output was invalid ({last_error}). Fix the JSON to strictly match the schema."
                )
                response = await self._llm.complete(
                    LLMRequest(
                        system=ANALYSIS_SYSTEM_PROMPT,
                        user=prompt,
                        expect_json=True,
                        temperature=0.0,
                    )
                )
                if response.finish_reason == "length":
                    last_error = "Model output was truncated (finish_reason=length)"
                    continue

                try:
                    manifest_out = ManifestOut.model_validate_json(response.text)
                    manifest = _to_domain_manifest(
                        repo, manifest_out, user_facts=user_facts
                    )
                    return {"manifest": manifest}
                except (ValidationError, ValueError) as exc:
                    last_error = str(exc)

            raise InvalidModelOutputError(
                f"Analysis agent failed to produce valid ManifestOut after {self._max_parse_retries + 1} attempts: {last_error}"
            )

        def route_after_reason(state: AnalysisAgentState) -> str:
            if state.get("done_exploring") or not state.get("pending_actions"):
                return "synthesize"
            return "act_tools"

        graph.add_node("bootstrap_tools", bootstrap_tools_node)
        graph.add_node("reason", reason_node)
        graph.add_node("act_tools", act_tools_node)
        graph.add_node("synthesize", synthesize_node)

        graph.add_edge(START, "bootstrap_tools")
        graph.add_edge("bootstrap_tools", "reason")
        graph.add_conditional_edges(
            "reason",
            route_after_reason,
            {"act_tools": "act_tools", "synthesize": "synthesize"},
        )
        graph.add_edge("act_tools", "reason")
        graph.add_edge("synthesize", END)

        return graph.compile()

    async def analyze(
        self,
        repo: RepositoryRef,
        *,
        validation_feedback: tuple[str, ...] = (),
        user_facts: tuple[UserFact, ...] = (),
    ) -> AnalysisManifest:
        toolset = RepositoryToolset(
            reader=self._reader,
            repo=repo,
            access_token=self._access_token,
        )
        compiled = self.build_graph(toolset)
        try:
            final_state = await compiled.ainvoke(
                {
                    "repo": repo,
                    "validation_feedback": validation_feedback,
                    "user_facts": user_facts,
                    "observations": [],
                    "step_count": 0,
                    "done_exploring": False,
                }
            )
        except InvalidModelOutputError as exc:
            raise AnalysisFailedError(str(exc)) from exc

        manifest: AnalysisManifest | None = final_state.get("manifest")
        if manifest is None:
            raise AnalysisFailedError("Analysis agent graph finished without producing a manifest")
        return manifest
