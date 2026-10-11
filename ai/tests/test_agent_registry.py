import pytest

from agents.base import BaseAgent
from agents.registry import available_agents, get_agent, register
from llm.client import FakeLLM


def test_available_agents_includes_support():
    assert "support" in available_agents()
    assert available_agents() == tuple(sorted(available_agents()))


def test_get_agent_constructs_support_agent():
    agent = get_agent("support", FakeLLM())

    assert isinstance(agent, BaseAgent)
    assert agent.name == "support"
    assert agent.prompt_name == "support_agent"


def test_get_agent_rejects_unknown_name():
    with pytest.raises(KeyError, match="Unknown agent"):
        get_agent("missing-agent", FakeLLM())


def test_register_rejects_empty_name():
    with pytest.raises(ValueError, match="must not be empty"):

        @register("   ")
        def build_empty_name(llm: FakeLLM) -> BaseAgent:
            return BaseAgent(
                name="empty",
                prompt_name="support_agent",
                llm=llm,
            )


def test_register_rejects_duplicate_name():
    @register("registry-test-unique")
    def first_factory(llm: FakeLLM) -> BaseAgent:
        return BaseAgent(
            name="first",
            prompt_name="support_agent",
            llm=llm,
        )

    with pytest.raises(ValueError, match="already registered"):

        @register("registry-test-unique")
        def second_factory(llm: FakeLLM) -> BaseAgent:
            return BaseAgent(
                name="second",
                prompt_name="support_agent",
                llm=llm,
            )
