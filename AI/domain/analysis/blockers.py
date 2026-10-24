from enum import StrEnum

from AI.domain.analysis.models import AnalysisManifest

MAX_MVP_COMPONENTS = 3


class Blocker(StrEnum):
    NO_RECOGNIZED_LANGUAGE = "no_recognized_language"
    NO_ENTRY_POINT = "no_entry_point"
    TOO_MANY_COMPONENTS = "too_many_components"

    @property
    def message(self) -> str:
        messages = {
            Blocker.NO_RECOGNIZED_LANGUAGE: "No recognized programming language was found in the repository.",
            Blocker.NO_ENTRY_POINT: "No application entry point or start command could be identified.",
            Blocker.TOO_MANY_COMPONENTS: f"Repository has more than {MAX_MVP_COMPONENTS} components (unsupported MVP scope).",
        }
        return messages[self]


def evaluate_blockers(report: AnalysisManifest) -> tuple[Blocker, ...]:
    """Rules that decide whether the analysis is enough to continue.

    These are plain business rules, so they are tested without an LLM.
    Adjust them here, not in the agent or the graph.
    """
    blockers: list[Blocker] = []

    has_language = bool(report.languages) or any(bool(c.language) for c in report.components)
    if not has_language:
        blockers.append(Blocker.NO_RECOGNIZED_LANGUAGE)

    has_entry = (
        bool(report.entry_points)
        or any(bool(c.start_cmd or c.build_cmd or c.output_dir) for c in report.components)
    )
    if not has_entry:
        blockers.append(Blocker.NO_ENTRY_POINT)

    if len(report.components) > MAX_MVP_COMPONENTS:
        blockers.append(Blocker.TOO_MANY_COMPONENTS)

    return tuple(blockers)
