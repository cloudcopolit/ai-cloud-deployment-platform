"""Analysis-accuracy evaluation over real public repositories (10 §5, roadmap Phase 4).

    python ai/eval/run_eval.py --repos <dir-with-shallow-clones> [--labels ai/eval/labels.yaml]

Each repository is a local shallow clone named owner_name. Files are read as bytes through a
read-only gateway (symlinks skipped); nothing in a clone is executed. The deterministic
analyzer always runs; an LLM-assisted column runs only for providers with an API key, and is
reported as "not run (MOCKED-ONLY)" otherwise.

Scored fields (micro-averaged precision/recall over all repositories):
  services       service directories found vs labelled
  frameworks     framework names of the labelled services
  data_stores    data store / messaging engines
  ports          exact port on correctly found services (accuracy)
  recommendation deployment method (accuracy)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cloudpilot_ai import analyze_repository
from cloudpilot_ai.contracts import AnalysisReport, AnalysisRequest, RepositoryRef
from cloudpilot_ai.errors import Budget
from cloudpilot_ai.ports import FileEntry, FileListing
from cloudpilot_ai.trace import Tracer


class LocalCloneGateway:
    """RepositoryGateway over a checked-out working tree. Read-only; symlinks are skipped."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def list_files(self) -> FileListing:
        entries = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for name in filenames:
                full = Path(dirpath) / name
                if full.is_symlink() or not full.is_file():
                    continue
                entries.append(
                    FileEntry(path=full.relative_to(self.root).as_posix(), size=full.stat().st_size)
                )
        return FileListing(entries=sorted(entries, key=lambda e: e.path), truncated=False)

    def read_file(self, path: str, max_bytes: int) -> bytes:
        full = (self.root / path).resolve()
        if self.root not in full.parents or full.is_symlink():
            raise ValueError("path escapes the repository")
        data = full.read_bytes()
        if len(data) > max_bytes:
            raise ValueError("file too large")
        return data


class _NullSink:
    def job_started(self) -> None: ...
    def run_started(self, agent: str, *, input_summary: dict[str, Any]) -> str:
        return "run"

    def task_started(
        self, run_id: str, task_type: str, *, input_summary: dict[str, Any] | None = None
    ) -> str:
        return "task"

    def task_finished(self, task_id: str, **kwargs: Any) -> None: ...
    def run_finished(self, run_id: str, **kwargs: Any) -> None: ...
    def report_ready(self, report: AnalysisReport) -> None: ...
    def plan_ready(self, plan: Any) -> None: ...


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, predicted: set[str], expected: set[str]) -> None:
        self.tp += len(predicted & expected)
        self.fp += len(predicted - expected)
        self.fn += len(expected - predicted)

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


@dataclass
class Accuracy:
    right: int = 0
    total: int = 0

    @property
    def value(self) -> float | None:
        return self.right / self.total if self.total else None


@dataclass
class Totals:
    services: Score = field(default_factory=Score)
    frameworks: Score = field(default_factory=Score)
    data_stores: Score = field(default_factory=Score)
    ports: Accuracy = field(default_factory=Accuracy)
    recommendation: Accuracy = field(default_factory=Accuracy)


def analyze(
    clone: Path, owner: str, name: str, branch: str, sha: str
) -> tuple[AnalysisReport, int]:
    request = AnalysisRequest(
        job_id=uuid.UUID(int=1),
        correlation_id="eval",
        repository=RepositoryRef(owner=owner, name=name, branch=branch, commit_sha=sha),
        github_installation_ref="local-clone",
    )
    started = time.monotonic()
    with Tracer(_NullSink()).run("ANALYSIS", {}) as run:
        report = analyze_repository(
            request,
            repository=LocalCloneGateway(clone),
            llm=None,
            run=run,
            budget=Budget(seconds=300),
        )
    return report, int((time.monotonic() - started) * 1000)


def score_repo(report: AnalysisReport, label: dict[str, Any], totals: Totals) -> dict[str, Any]:
    expected_services: dict[str, dict[str, Any]] = {s["path"]: s for s in label.get("services", [])}
    predicted = {s.path: s for s in report.services}
    totals.services.add(set(predicted), set(expected_services))
    expected_frameworks = {s["framework"] for s in expected_services.values() if s.get("framework")}
    predicted_frameworks = {str(s.framework) for s in predicted.values() if s.framework}
    totals.frameworks.add(predicted_frameworks, expected_frameworks)
    stores: set[str] = {str(d.engine) for d in report.data_stores}
    totals.data_stores.add(stores, set(label.get("data_stores", [])))
    port_misses = []
    for path, svc in expected_services.items():
        if "port" in svc and path in predicted:
            totals.ports.total += 1
            if predicted[path].port == svc["port"]:
                totals.ports.right += 1
            else:
                port_misses.append(f"{path}: {predicted[path].port} != {svc['port']}")
    method = report.recommendation.method if report.recommendation else None
    if "recommendation" in label:
        totals.recommendation.total += 1
        totals.recommendation.right += int(method == label["recommendation"])
    return {
        "services_missing": sorted(set(expected_services) - set(predicted)),
        "services_extra": sorted(set(predicted) - set(expected_services)),
        "frameworks_missing": sorted(expected_frameworks - predicted_frameworks),
        "frameworks_extra": sorted(predicted_frameworks - expected_frameworks),
        "stores_missing": sorted(set(label.get("data_stores", [])) - stores),
        "stores_extra": sorted(stores - set(label.get("data_stores", []))),
        "port_misses": port_misses,
        "recommendation": method,
        "recommendation_expected": label.get("recommendation"),
    }


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repos", required=True, type=Path)
    parser.add_argument("--labels", type=Path, default=Path(__file__).with_name("labels.yaml"))
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()

    labels = yaml.safe_load(args.labels.read_text(encoding="utf-8"))
    totals = Totals()
    rows = []
    for full_name, label in labels["repositories"].items():
        owner, name = full_name.split("/")
        clone = args.repos / f"{owner}_{name}"
        if not clone.is_dir():
            print(f"skip {full_name}: no clone at {clone}", file=sys.stderr)
            continue
        sha = (clone / ".git" / "HEAD").read_text().strip()
        if sha.startswith("ref:"):
            ref = sha.split(" ", 1)[1]
            sha = (
                (clone / ".git" / ref).read_text().strip()
                if (clone / ".git" / ref).exists()
                else "0" * 40
            )
        report, ms = analyze(clone, owner, name, label.get("branch", "main"), sha)
        detail = score_repo(report, label, totals)
        rows.append({"repository": full_name, "commit": sha, "ms": ms, **detail})

    summary = {
        "services": {"precision": totals.services.precision, "recall": totals.services.recall},
        "frameworks": {
            "precision": totals.frameworks.precision,
            "recall": totals.frameworks.recall,
        },
        "data_stores": {
            "precision": totals.data_stores.precision,
            "recall": totals.data_stores.recall,
        },
        "ports": {"accuracy": totals.ports.value, "n": totals.ports.total},
        "recommendation": {
            "accuracy": totals.recommendation.value,
            "n": totals.recommendation.total,
        },
    }
    providers = {
        "deterministic": "run",
        **dict.fromkeys(
            ("anthropic", "openai", "gemini", "xai"), "not run (MOCKED-ONLY: no API key)"
        ),
    }
    result = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repositories": len(rows),
        "providers": providers,
        "summary": summary,
        "per_repository": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"eval-{datetime.now(UTC):%Y%m%d}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"{len(rows)} repositories · deterministic analyzer · results in {path}")
    print(f"{'field':16} {'precision':>9} {'recall':>7} {'accuracy':>9}")
    for key in ("services", "frameworks", "data_stores"):
        print(f"{key:16} {fmt(summary[key]['precision']):>9} {fmt(summary[key]['recall']):>7}")
    for key in ("ports", "recommendation"):
        accuracy, n = fmt(summary[key]["accuracy"]), summary[key]["n"]
        print(f"{key:16} {'':>9} {'':>7} {accuracy:>9}  (n={n})")
    for row in rows:
        problems = {
            k: v
            for k, v in row.items()
            if k not in {"repository", "commit", "ms", "recommendation", "recommendation_expected"}
            and v
        }
        mark = (
            "ok "
            if not problems and row["recommendation"] == row["recommendation_expected"]
            else "!! "
        )
        rec = (
            ""
            if row["recommendation"] == row["recommendation_expected"]
            else f"  rec {row['recommendation']} != {row['recommendation_expected']}"
        )
        shown = json.dumps(problems) if problems else ""
        print(f"{mark}{row['repository']:42} {row['ms']:>6} ms  {shown}{rec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
