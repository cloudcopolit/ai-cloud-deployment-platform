from agents.base import BaseAgent
from llm.client import FakeLLM


def test_base_agent_renders_prompt_and_calls_llm():
    agent = BaseAgent(
        name="support",
        prompt_name="support_agent",
        llm=FakeLLM(),
    )

    result = agent.run("hello", product="Acme")

    assert result == "[fake] hello"
