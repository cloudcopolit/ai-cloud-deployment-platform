from __future__ import annotations

from dataclasses import replace

from AI.application.aws_detection.config_scanner import AwsConfigScanner
from AI.application.ports.agents import AwsRequirementsDetector
from AI.domain.analysis.models import AnalysisManifest
from AI.domain.aws_detection.models import AwsConfigKind, AwsRequirementsResult
from AI.domain.shared.errors import AnalysisFailedError

REGION_QUESTION = "Which AWS region should this application be deployed to?"


class DetectAwsRequirements:
    """Use case: AnalysisManifest -> AwsRequirementsResult.

    1. Deterministic scan for AWS config signals (no LLM).
    2. Delegate service detection to the AwsRequirementsDetector port (the agent).
    3. Apply business rules that must not depend on the model.
    """

    def __init__(self, scanner: AwsConfigScanner, detector: AwsRequirementsDetector) -> None:
        self._scanner = scanner
        self._detector = detector

    async def execute(self, manifest: AnalysisManifest) -> AwsRequirementsResult:
        scan = await self._scanner.scan(manifest.repo)
        result = await self._detector.detect(manifest, scan.status)

        # Guard against a detector answering for a different repo or commit.
        if result.repo != manifest.repo:
            raise AnalysisFailedError(
                f"AWS detection returned a result for {result.repo.full_name}@{result.repo.commit_sha}, "
                f"expected {manifest.repo.full_name}@{manifest.repo.commit_sha}"
            )

        clarifications = list(result.clarifications)
        needs_region = bool(result.requirements) and not scan.status.has(
            AwsConfigKind.REGION_SETTING
        )
        if needs_region and REGION_QUESTION not in clarifications:
            clarifications.append(REGION_QUESTION)

        if tuple(clarifications) == result.clarifications:
            return result
        return replace(result, clarifications=tuple(clarifications))
