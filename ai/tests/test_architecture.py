"""The deterministic Architect: archetype fit, real prices, different plans for different repos."""

from __future__ import annotations

import json
import uuid

import pytest
from cloudpilot_ai.architecture import container_postgres, design_architecture
from cloudpilot_ai.architecture.pricing import HOURS_PER_MONTH, load_prices
from cloudpilot_ai.contracts import AnalysisReport, ArchitecturePlan, ComponentType

from tests import fixture_repos as repos
from tests.test_analysis_golden import analyze

ANALYSIS_ID = uuid.UUID(int=42)

NODE_PG = {
    "package.json": '{"name":"orders-api","scripts":{"start":"node server.js"},'
    '"dependencies":{"express":"4.21.0","pg":"8.13.0"}}',
    "server.js": 'const app = require("express")();\napp.get("/healthz", (q, r) => r.send("ok"));\n'
    "app.listen(process.env.PORT || 3000);\n",
    "Dockerfile": 'FROM node:22-alpine\nCOPY . .\nEXPOSE 3000\nCMD ["node","server.js"]\n',
}

FASTAPI_REDIS = repos.FASTAPI_POSTGRES | {
    "requirements.txt": repos.FASTAPI_POSTGRES["requirements.txt"] + "redis==5.0.8\n"
}


def plan_for(files: dict[str, str]) -> tuple[AnalysisReport, ArchitecturePlan]:
    report = analyze(files)
    return report, design_architecture(report, source_analysis_id=ANALYSIS_ID)


def component(plan: ArchitecturePlan, type_: ComponentType):
    [found] = [c for c in plan.components if c.type == type_]
    return found


def test_price_table_is_the_generated_aws_one() -> None:
    table = load_prices("us-east-1")
    assert table.source.startswith("AWS Price List")
    assert table.pricing_as_of[:4].isdigit()
    for key in ("fargate_vcpu_hour", "alb_hour", "rds_postgres_t4g_micro_hour", "public_ipv4_hour"):
        assert table[key].usd > 0
        assert table[key].sku


def test_fastapi_postgres_gets_an_automated_plan_priced_from_the_table() -> None:
    _, plan = plan_for(repos.FASTAPI_POSTGRES)
    assert (plan.archetype, plan.automated, plan.schema_version) == (
        "container-postgres",
        True,
        "1.1",
    )
    app = component(plan, ComponentType.ECS_SERVICE)
    assert app.config["container_port"] == 8000
    assert app.config["health_path"] == "/health"
    assert (app.config["cpu"], app.config["memory"]) == (256, 512)
    assert "JWT_SECRET" in app.config["env_names"]  # needed by the app, supplied by the user
    assert "DATABASE_URL" not in app.config["env_names"]  # provided by the deployment
    assert component(plan, ComponentType.RDS).config["instance_class"] == "db.t4g.micro"

    table = load_prices("us-east-1")
    assert plan.cost.pricing_as_of == table.pricing_as_of
    by_id = {line.component_id: line.monthly_usd for line in plan.cost.lines}
    expected_db = round(
        table["rds_postgres_t4g_micro_hour"].usd * HOURS_PER_MONTH
        + table["rds_gp3_gb_month"].usd * container_postgres.DB_STORAGE_GB,
        2,
    )
    assert by_id["db"] == pytest.approx(expected_db, abs=0.011)
    assert plan.cost.monthly_total == pytest.approx(sum(by_id.values()), abs=0.01)
    assert not plan.security.encryption_in_transit  # HTTP only, stated honestly
    assert {r.code for r in plan.risks} >= {"HTTP_ONLY", "SINGLE_TASK", "NO_DB_BACKUPS"}


def test_different_repositories_get_different_plans() -> None:
    _, py = plan_for(repos.FASTAPI_POSTGRES)
    _, node = plan_for(NODE_PG)
    a, b = component(py, ComponentType.ECS_SERVICE), component(node, ComponentType.ECS_SERVICE)
    assert node.automated
    assert (a.config["container_port"], a.config["health_path"]) == (8000, "/health")
    assert (b.config["container_port"], b.config["health_path"]) == (3000, "/healthz")
    assert a.id != b.id


def test_the_same_report_always_gives_the_same_plan() -> None:
    report = analyze(repos.FASTAPI_POSTGRES)
    first = design_architecture(report, source_analysis_id=ANALYSIS_ID)
    second = design_architecture(report, source_analysis_id=ANALYSIS_ID)
    assert first == second


@pytest.mark.parametrize(
    ("files", "reason"),
    [
        (FASTAPI_REDIS, "other data stores are not automated yet: redis"),
        (repos.EXPRESS_MONGO, "it needs PostgreSQL"),
        (repos.STATIC_SITE, "not a container"),
        (repos.MONOREPO_KAFKA, "exactly one HTTP service"),
    ],
)
def test_reports_outside_the_archetype_fall_back_and_say_why(
    files: dict[str, str], reason: str
) -> None:
    _, plan = plan_for(files)
    assert not plan.automated
    assert plan.archetype is None
    note = plan.risks[0]
    assert note.code == "NOT_AUTOMATED"
    assert reason in note.message


def test_a_region_without_a_price_table_is_not_automated() -> None:
    report = analyze(repos.FASTAPI_POSTGRES)
    plan = design_architecture(report, source_analysis_id=ANALYSIS_ID, region="eu-west-1")
    assert not plan.automated
    assert "no price table for eu-west-1" in plan.risks[0].message


def test_v1_0_plans_stored_before_the_upgrade_still_load() -> None:
    _, plan = plan_for(repos.FASTAPI_POSTGRES)
    stored = plan.model_dump(mode="json", exclude={"archetype", "automated"}) | {
        "schema_version": "1.0"
    }
    # stored as JSON and read back the way the backend reads it
    loaded = ArchitecturePlan.model_validate_json(json.dumps(stored))
    assert (loaded.automated, loaded.archetype) == (False, None)
