from agents.base import BaseAgent
from agents.registry import register
from llm.client import LLMClient


@register("support")
def build(llm: LLMClient) -> BaseAgent:
    return BaseAgent(name="support", prompt_name="support_agent", llm=llm)
