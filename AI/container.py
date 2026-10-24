from AI.agents.analysis.agent import LangGraphAnalysisAgent
from AI.agents.validator.agent import RepositoryManifestValidator
from AI.application.ports.llm_provider import LLMProvider
from AI.application.ports.repository_reader import RepositoryReader
from AI.core.config import Settings
from AI.infrastructure.github.github_repository_reader import GitHubRepositoryReader
from AI.infrastructure.llm.gemini_provider import GeminiProvider


def build_llm(settings: Settings) -> LLMProvider:
    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def build_repository_reader() -> RepositoryReader:
    return GitHubRepositoryReader()


def build_analysis_agent(
    *,
    llm: LLMProvider,
    reader: RepositoryReader,
    access_token: str = "",
) -> LangGraphAnalysisAgent:
    return LangGraphAnalysisAgent(llm=llm, reader=reader, access_token=access_token)


def build_manifest_validator(
    *,
    reader: RepositoryReader,
    access_token: str = "",
) -> RepositoryManifestValidator:
    return RepositoryManifestValidator(reader=reader, access_token=access_token)
