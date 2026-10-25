"""Mutable accumulator the detectors write into; `assemble` turns it into an AnalysisReport."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import Literal

from cloudpilot_ai.analysis.snapshot import Snapshot
from cloudpilot_ai.contracts import (
    ConfigFile,
    DataStore,
    Dependency,
    EntryPoint,
    EnvVar,
    Evidence,
    Finding,
    MissingInfo,
    ServiceType,
    Severity,
    UnsupportedTechnology,
)

MAX_EVIDENCE = 10
ConfigKind = Literal[
    "dockerfile", "compose", "ci", "terraform", "env_example", "k8s", "build", "other"
]


def directory_of(path: str) -> str:
    return posixpath.dirname(path) or "."


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, max(0, index)) + 1


@dataclass
class ServiceCandidate:
    root: str  # directory, "." for the repository root
    name: str
    language: str | None = None
    framework: str | None = None
    framework_kind: str = "other"
    service_type: ServiceType | None = None
    port: int | None = None
    port_confidence: float = 0.0
    port_source: str | None = None
    dockerfile: str | None = None
    entry_command: str | None = None
    health: str | None = None
    static_site: bool = False
    needs_build: bool = False
    compose_name: str | None = None
    manifest: str | None = None
    confidence: float = 0.5
    evidence: list[Evidence] = field(default_factory=list)

    def add_evidence(self, ev: Evidence) -> None:
        if len(self.evidence) < MAX_EVIDENCE and ev not in self.evidence:
            self.evidence.append(ev)

    def set_port(self, port: int, confidence: float, source: str) -> None:
        if 0 < port < 65536 and confidence > self.port_confidence:
            self.port, self.port_confidence, self.port_source = port, confidence, source


@dataclass
class FrameworkHit:
    name: str
    kind: str
    version: str | None
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Facts:
    snapshot: Snapshot
    repo_name: str
    services: dict[str, ServiceCandidate] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    frameworks: dict[str, FrameworkHit] = field(default_factory=dict)
    data_stores: dict[str, DataStore] = field(default_factory=dict)
    env_vars: dict[str, EnvVar] = field(default_factory=dict)
    config_files: list[ConfigFile] = field(default_factory=list)
    entry_points: list[EntryPoint] = field(default_factory=list)
    blockers: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    missing: list[MissingInfo] = field(default_factory=list)
    unsupported: list[UnsupportedTechnology] = field(default_factory=list)
    workspace_roots: set[str] = field(default_factory=set)  # monorepo roots (npm workspaces…)

    # ───────────── helpers ─────────────
    def evidence(self, path: str, detector: str, line: int | None = None) -> Evidence:
        return Evidence(
            file_path=path[:1024],
            line_start=line,
            line_end=line,
            detector=detector[:255],
            content_sha256=self.snapshot.sha(path),
        )

    def service(self, root: str, *, default_name: str | None = None) -> ServiceCandidate:
        root = root or "."
        if root not in self.services:
            name = default_name or (self.repo_name if root == "." else posixpath.basename(root))
            self.services[root] = ServiceCandidate(root=root, name=name[:255])
        return self.services[root]

    def framework(
        self, name: str, kind: str, version: str | None, confidence: float, ev: Evidence
    ) -> None:
        hit = self.frameworks.get(name)
        if hit is None:
            hit = self.frameworks[name] = FrameworkHit(name, kind, version, confidence)
        hit.confidence = max(hit.confidence, confidence)
        hit.version = hit.version or version
        if len(hit.evidence) < MAX_EVIDENCE:
            hit.evidence.append(ev)

    def data_store(self, engine: str, inferred_from: str, confidence: float, ev: Evidence) -> None:
        current = self.data_stores.get(engine)
        if current is None:
            self.data_stores[engine] = DataStore(
                engine=engine,  # type: ignore[arg-type]
                inferred_from=inferred_from[:255],
                confidence=confidence,
                evidence=[ev],
            )
            return
        evidence = list(current.evidence)
        if len(evidence) < MAX_EVIDENCE and ev not in evidence:
            evidence.append(ev)
        self.data_stores[engine] = current.model_copy(
            update={"confidence": max(current.confidence, confidence), "evidence": evidence}
        )

    def env(self, name: str, referenced_in: str, *, required: bool = True) -> None:
        if not name or len(name) > 128 or not name.replace("_", "").isalnum() or not name.isupper():
            return
        if name[0].isdigit():
            return
        if name not in self.env_vars:
            self.env_vars[name] = EnvVar(
                name=name, required=required, referenced_in=referenced_in[:255]
            )

    def config(self, path: str, kind: ConfigKind, detector: str) -> None:
        if any(c.path == path for c in self.config_files) or len(self.config_files) >= 200:
            return
        self.config_files.append(
            ConfigFile(
                path=path, kind=kind, confidence=1.0, evidence=[self.evidence(path, detector)]
            )
        )

    def entry(self, path: str, command: str | None, confidence: float, detector: str) -> None:
        if any(e.path == path and e.command == command for e in self.entry_points):
            return
        if len(self.entry_points) < 100:
            self.entry_points.append(
                EntryPoint(
                    path=path,
                    command=(command or None) and command[:255],
                    confidence=confidence,
                    evidence=[self.evidence(path, detector)],
                )
            )

    def finding(
        self,
        code: str,
        severity: Severity,
        message: str,
        *,
        evidence: list[Evidence] | None = None,
        action: str | None = None,
    ) -> None:
        bucket = self.blockers if severity is Severity.BLOCKER else self.warnings
        if any(f.code == code and f.message == message for f in bucket):
            return
        bucket.append(
            Finding(
                code=code,
                severity=severity,
                message=message[:500],
                evidence=(evidence or [])[:MAX_EVIDENCE],
                suggested_action=action[:500] if action else None,
            )
        )

    def ask(self, key: str, question: str, *, required: bool = True) -> None:
        if not any(m.key == key for m in self.missing):
            self.missing.append(
                MissingInfo(key=key[:255], question=question[:500], required=required)
            )

    def unsupported_tech(self, name: str, reason: str) -> None:
        if not any(u.name == name for u in self.unsupported):
            self.unsupported.append(UnsupportedTechnology(name=name[:255], reason=reason[:500]))
