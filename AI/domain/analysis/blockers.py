from enum import StrEnum

from AI.domain.analysis.models import AnalysisReport


class Blocker(StrEnum):
    def __init__(self, message: str):
        self.message = message
    NO_RECOGNIZED_LANGUAGE = "no_recognized_language"
    NO_ENTRY_POINT = "no_entry_point"


def evaluate_blockers(report: AnalysisReport) -> tuple[Blocker, ...]:
    """Rules that decide whether the analysis is enough to continue.

    These are plain business rules, so they are tested without an LLM.
    Adjust them here, not in the agent or the graph.
    """
    blockers: list[Blocker] = []
    if not report.languages:
        blockers.append(Blocker.NO_RECOGNIZED_LANGUAGE)
    if not report.entry_points:
        blockers.append(Blocker.NO_ENTRY_POINT)
    return tuple(blockers)