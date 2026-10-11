from dataclasses import dataclass

from llm.client import LLMClient
from prompts.loader import render


@dataclass
class BaseAgent:
    name: str
    prompt_name: str
    llm: LLMClient

    def system_prompt(self, **variables: str) -> str:
        return render(self.prompt_name, **variables)

    def run(self, user_input: str, **variables: str) -> str:
        return self.llm.complete(
            system=self.system_prompt(**variables),
            user=user_input,
        )
