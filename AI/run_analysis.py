#!/usr/bin/env python3
"""CLI runner to test the LangGraph Analysis + Validator pipeline on a local folder or GitHub repo."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
import os
import sys
from uuid import uuid4

from AI.agents.analysis.agent import LangGraphAnalysisAgent
from AI.agents.validator.agent import RepositoryManifestValidator
from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.application.analysis.pdf_report import generate_user_pdf_report
from AI.core.config import Settings
from AI.domain.analysis.models import RepositoryRef
from AI.infrastructure.github.github_repository_reader import GitHubRepositoryReader
from AI.infrastructure.github.local_repository_reader import LocalRepositoryReader
from AI.infrastructure.llm.gemini_provider import GeminiProvider
from AI.orchestration.graph import build_orchestrator
from AI.test.fakes import FakeStore


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the CloudPilot Analysis + Validator agents on a local folder or GitHub repository."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--local",
        type=str,
        help="Path to a local project directory to analyze.",
    )
    group.add_argument(
        "--github",
        type=str,
        help="GitHub repository in 'owner/name' format.",
    )
    parser.add_argument(
        "--commit",
        type=str,
        default="HEAD",
        help="Commit SHA or branch ref (default: HEAD).",
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="Optional GitHub access token for private repos or higher rate limits.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional path to save the generated JSON report.",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default="",
        help="Optional path to save the human-readable PDF report for the user.",
    )
    args = parser.parse_args()

    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:
        print(
            "ERROR: Missing GEMINI_API_KEY. Set GEMINI_API_KEY in your environment or .env file.\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    llm = GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    if args.local:
        reader = LocalRepositoryReader(args.local)
        folder_name = os.path.basename(os.path.abspath(args.local))
        repo_ref = RepositoryRef(owner="local", name=folder_name, commit_sha=args.commit)
    else:
        if "/" not in args.github:
            print("ERROR: --github must be in 'owner/repo' format.", file=sys.stderr)
            sys.exit(1)
        owner, name = args.github.split("/", 1)
        reader = GitHubRepositoryReader()  # type: ignore[assignment]
        repo_ref = RepositoryRef(owner=owner, name=name, commit_sha=args.commit)

    agent = LangGraphAnalysisAgent(
        llm=llm,
        reader=reader,
        access_token=args.github_token,
    )
    validator = RepositoryManifestValidator(
        reader=reader,
        access_token=args.github_token,
    )
    store = FakeStore()

    graph = build_orchestrator(
        analyze=AnalyzeRepository(agent),
        validator=validator,
        store=store,
    )

    print(f"Analyzing {repo_ref.full_name}@{repo_ref.commit_sha} using {settings.gemini_model}...")
    final_state = await graph.ainvoke({"run_id": uuid4(), "repo": repo_ref})

    if final_state.get("error_code"):
        print(f"Run failed with error_code: {final_state['error_code']}", file=sys.stderr)
        sys.exit(1)

    outcome = final_state["outcome"]
    manifest_dict = asdict(outcome.report)
    manifest_dict["id"] = str(manifest_dict["id"])
    manifest_dict["created_at"] = outcome.report.created_at.isoformat()
    manifest_dict["final_status"] = str(store.statuses[-1][0]) if store.statuses else "unknown"
    manifest_dict["blockers"] = [str(b) for b in outcome.blockers]

    report_json = json.dumps(manifest_dict, indent=2)
    print("\n================ GENERATED ANALYSIS MANIFEST ================\n")
    print(report_json)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"\nSaved JSON report to {args.output}")

    if args.pdf:
        pdf_path = generate_user_pdf_report(
            outcome.report,
            args.pdf,
            final_status=str(store.statuses[-1][0]) if store.statuses else "succeeded",
            blockers=outcome.blockers,
        )
        print(f"Saved user-readable PDF report to {pdf_path}")


if __name__ == "__main__":
    asyncio.run(main())
