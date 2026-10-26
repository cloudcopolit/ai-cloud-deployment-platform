"""LLM provider status endpoint and health CLI: without keys every provider is MOCKED-ONLY."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import llm_health
from app.core.config import settings
from app.integrations import llm
from tests.factories import headers_for, make_user


def test_providers_without_keys_are_mocked_only(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    for provider in llm.PROVIDERS:
        monkeypatch.setattr(settings, f"{provider}_api_key", None)
    user = make_user(db_session)
    rows = client.get("/llm/providers?refresh=true", headers=headers_for(user)).json()
    assert [(r["provider"], r["mode"], r["configured"]) for r in rows] == [
        ("anthropic", "MOCKED-ONLY", False),
        ("openai", "MOCKED-ONLY", False),
        ("gemini", "MOCKED-ONLY", False),
        ("xai", "MOCKED-ONLY", False),
    ]
    assert client.get("/llm/providers").status_code == 401


def test_priority_prices_and_overrides_come_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_provider_priority", "xai,openai")
    monkeypatch.setattr(settings, "llm_price_openai", "1.5,6")
    monkeypatch.setattr(settings, "llm_price_xai", "not-a-price")
    monkeypatch.setattr(settings, "llm_model_openai", "some-model")
    config = llm.gateway_config()
    assert config.priority == ["xai", "openai"]
    assert config.prices == {"openai": (1.5, 6.0)}
    assert config.model_overrides["openai"] == "some-model"


def test_health_cli_without_keys_exits_nonzero(monkeypatch, capsys) -> None:
    for provider in llm.PROVIDERS:
        monkeypatch.setattr(settings, f"{provider}_api_key", None)
    assert llm_health.main(["--json"]) == 1
    out = capsys.readouterr().out
    assert '"mode": "MOCKED-ONLY"' in out
