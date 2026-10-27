"""Provider health check: `python -m app.llm_health` (add --probe for one tiny real call each).

Prints which LLM providers are REAL or MOCKED-ONLY, whether their list-models endpoint answers,
and which model the selection policy picks. Never prints keys.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from cloudpilot_ai.llm import MultiProviderGateway
from pydantic import BaseModel

from app.integrations.llm import build_gateway, gateway_config


class _Probe(BaseModel):
    ok: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe", action="store_true", help="make one minimal completion per provider"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    rows = [row.__dict__ for row in build_gateway().health()]
    if args.probe:
        for row in rows:
            if row["mode"] != "REAL" or not row["chosen_model"]:
                continue
            single = dataclasses.replace(
                gateway_config(), priority=[row["provider"]], max_calls_per_job=2
            )
            try:
                answer = MultiProviderGateway(single).complete_json(
                    task="health_probe",
                    system="Health check.",
                    user='Return the JSON object {"ok": true}.',
                    schema=_Probe,
                )
                row["probe"] = {
                    "ok": True,
                    "tokens": answer.usage.input_tokens + answer.usage.output_tokens,
                }
            except Exception as exc:  # report, never crash the check
                row["probe"] = {"ok": False, "error": type(exc).__name__}
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'provider':10} {'mode':12} {'reachable':9} {'models':6} {'chosen model':40} error")
        for r in rows:
            print(
                f"{r['provider']:10} {r['mode']:12} {r['reachable']!s:9} {r['models_listed']!s:6} "
                f"{r['chosen_model']!s:40} {r['error'] or ''}"
                + (f"  probe={r['probe']}" if "probe" in r else "")
            )
    return 0 if any(r["mode"] == "REAL" and r["reachable"] for r in rows) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
