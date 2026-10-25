from __future__ import annotations

from uuid import UUID

from AI.application.aws_detection.detect_aws_requirements import DetectAwsRequirements
from AI.application.communication.message_router import (
    AgentMessage,
    AgentRole,
    MessageKind,
    MessageRouter,
)
from AI.domain.analysis.models import AnalysisManifest
from AI.domain.aws_detection.models import AwsRequirementsResult
from AI.domain.shared.errors import AnalysisFailedError


class AgentCoordinator:
    """Adapter between orchestrator nodes and agents, speaking only through the MessageRouter.

    Messages carry IDs. The coordinator keeps the actual immutable records for the duration of
    one request so nothing but references travels in a message.
    """

    def __init__(self, *, router: MessageRouter, detect_aws: DetectAwsRequirements) -> None:
        self._router = router
        self._detect_aws = detect_aws
        self._manifests: dict[UUID, AnalysisManifest] = {}
        self._aws_results: dict[UUID, AwsRequirementsResult] = {}
        router.register(AgentRole.AWS_DETECTION, self._handle_aws_detection)

    async def request_aws_detection(
        self, run_id: UUID, manifest: AnalysisManifest
    ) -> AwsRequirementsResult:
        """Orchestrator -> AWS detection agent -> orchestrator. Raises AnalysisFailedError on failure."""
        self._manifests[manifest.id] = manifest
        request = AgentMessage.create(
            run_id=run_id,
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.AWS_DETECTION,
            kind=MessageKind.AWS_DETECTION_REQUEST,
            payload={"manifest_id": str(manifest.id)},
        )
        try:
            reply = await self._router.send(request)
            if reply is None:
                raise AnalysisFailedError("AWS detection agent returned no reply")
            if reply.kind is MessageKind.FAILURE:
                raise AnalysisFailedError(
                    f"AWS detection failed: {reply.get('error_code', 'unknown')}"
                )
            result = self._aws_results.get(request.id)
            if result is None:
                raise AnalysisFailedError("AWS detection reply did not reference a stored result")
            return result
        finally:
            self._manifests.pop(manifest.id, None)
            self._aws_results.pop(request.id, None)

    async def _handle_aws_detection(self, message: AgentMessage) -> AgentMessage:
        try:
            manifest = self._manifests.get(UUID(message.get("manifest_id")))
        except ValueError:
            manifest = None

        if manifest is None:
            return AgentMessage.create(
                run_id=message.run_id,
                sender=AgentRole.AWS_DETECTION,
                recipient=AgentRole.ORCHESTRATOR,
                kind=MessageKind.FAILURE,
                payload={"error_code": "manifest_not_found"},
                in_reply_to=message.id,
            )

        result = await self._detect_aws.execute(manifest)
        self._aws_results[message.id] = result
        return AgentMessage.create(
            run_id=message.run_id,
            sender=AgentRole.AWS_DETECTION,
            recipient=AgentRole.ORCHESTRATOR,
            kind=MessageKind.AWS_DETECTION_COMPLETED,
            payload={
                "result_ref": str(message.id),
                "requirement_count": str(len(result.requirements)),
            },
            in_reply_to=message.id,
        )
