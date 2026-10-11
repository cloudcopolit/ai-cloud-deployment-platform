"""LLM-backed architecture proposal agent."""

import json
from collections.abc import Mapping
from typing import Any

from agents.architecture.models import ArchitectureComponent, ArchitectureProposal
from agents.base import BaseAgent
from agents.code_analyzer.repository_analyzer import RepositoryAnalysis
from llm.client import LLMClient


class ArchitectureAgent:
    """Generate a structured architecture proposal from repository analysis."""

    def __init__(self, llm: LLMClient) -> None:
        self._agent = BaseAgent(
            name="architecture",
            prompt_name="architecture_agent",
            llm=llm,
        )

    def run(
        self,
        repository: RepositoryAnalysis,
        *,
        requirements: str = "",
    ) -> ArchitectureProposal:
        """Generate and validate an architecture proposal."""
        payload = {
            "project_name": repository.project_name,
            "languages": list(repository.languages),
            "project_structure": repository.project_structure,
            "entry_points": list(repository.entry_points),
            "dependencies": list(repository.dependencies),
            "frameworks": list(repository.frameworks),
            "config_files": list(repository.config_files),
            "requirements": requirements,
        }

        response = self._agent.run(
            json.dumps(payload, ensure_ascii=False),
        )
        data = self._parse_response(response)

        return ArchitectureProposal(
            project_name=repository.project_name,
            summary=self._required_string(data, "summary"),
            components=self._components(data.get("components", [])),
            interactions=self._string_tuple(data, "interactions"),
            deployment_requirements=self._string_tuple(
                data,
                "deployment_requirements",
            ),
            assumptions=self._string_tuple(data, "assumptions"),
            open_questions=self._string_tuple(data, "open_questions"),
        )

    @staticmethod
    def _parse_response(response: str) -> dict[str, Any]:
        """Parse a JSON object returned by the language model."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError("Architecture response must be valid JSON") from exc

        if not isinstance(data, dict):
            raise ValueError("Architecture response must be a JSON object")

        return data

    @staticmethod
    def _required_string(data: Mapping[str, Any], key: str) -> str:
        """Return a required non-empty string field."""
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Architecture field '{key}' must be a non-empty string")
        return value

    @classmethod
    def _string_tuple(
        cls,
        data: Mapping[str, Any],
        key: str,
    ) -> tuple[str, ...]:
        """Validate and convert a list of non-empty strings."""
        value = data.get(key, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"Architecture field '{key}' must be a list of strings")
        return tuple(value)

    @classmethod
    def _components(cls, value: Any) -> tuple[ArchitectureComponent, ...]:
        """Validate and convert proposed architecture components."""
        if not isinstance(value, list):
            raise ValueError("Architecture field 'components' must be a list")

        components = []
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("Each architecture component must be an object")

            technology = item.get("technology")
            if technology is not None and not isinstance(technology, str):
                raise ValueError(
                    "Component field 'technology' must be a string or null"
                )

            if isinstance(technology, str) and not technology.strip():
                raise ValueError("Component field 'technology' must not be empty")

            components.append(
                ArchitectureComponent(
                    name=cls._required_string(item, "name"),
                    responsibility=cls._required_string(item, "responsibility"),
                    technology=technology,
                )
            )

        return tuple(components)
