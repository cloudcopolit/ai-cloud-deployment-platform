from __future__ import annotations

from dataclasses import replace

from AI.application.ports.repository_reader import RepositoryReader
from AI.domain.analysis.models import (
    AnalysisManifest,
    ComponentSpec,
    ComponentType,
    OpenQuestion,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class RepositoryManifestValidator:
    """Validator Agent that verifies an AnalysisManifest against repository files.

    Enforces CloudPilot's safety and provenance rules:
    1. Cited evidence files must actually exist in the repository.
    2. Critical fields (port, start_cmd, build_cmd) must have supporting evidence or appear in repo files.
    3. If `finalize_unresolved=True` (after bounded retries), any unverified field is demoted
       to `None` with confidence 0.0 and converted into an `OpenQuestion` so the pipeline never guesses.
    """

    def __init__(self, reader: RepositoryReader, access_token: str = "") -> None:
        self._reader = reader
        self._access_token = access_token

    async def validate(
        self,
        manifest: AnalysisManifest,
        *,
        finalize_unresolved: bool = False,
    ) -> ValidationResult:
        repo_files = set(await self._reader.list_files(manifest.repo, self._access_token))
        file_cache: dict[str, str] = {}

        async def _get_file_text(path: str) -> str:
            if path not in file_cache:
                file_cache[path] = await self._reader.read_file(
                    manifest.repo, path, self._access_token
                )
            return file_cache[path]

        issues: list[ValidationIssue] = []
        updated_components: list[ComponentSpec] = []
        new_questions: list[OpenQuestion] = list(manifest.open_questions)
        existing_question_keys = {(q.component, q.field_path) for q in new_questions}

        for comp in manifest.components:
            comp_issues: list[ValidationIssue] = []
            valid_evidence = []
            evidenced_fields: set[str] = set()

            for ev in comp.evidence:
                clean_file = ev.file.lstrip("/")
                if clean_file not in repo_files:
                    comp_issues.append(
                        ValidationIssue(
                            component=comp.name,
                            field=ev.field,
                            message=f"Evidence cites non-existent file '{ev.file}'.",
                            severity=ValidationSeverity.ERROR,
                        )
                    )
                else:
                    valid_evidence.append(ev)
                    evidenced_fields.add(ev.field)

            # Check server port provenance
            port = comp.port
            start_cmd = comp.start_cmd
            build_cmd = comp.build_cmd
            confidence = dict(comp.field_confidence)

            if port is not None and confidence.get("port", 0.0) < 1.0:
                if "port" not in evidenced_fields:
                    comp_issues.append(
                        ValidationIssue(
                            component=comp.name,
                            field="port",
                            message=f"Port {port} has no valid file evidence citation.",
                            severity=ValidationSeverity.ERROR,
                        )
                    )
                else:
                    # Verify the port number appears in at least one cited evidence file for port
                    port_ev_files = [
                        ev.file.lstrip("/")
                        for ev in valid_evidence
                        if ev.field == "port" and ev.file.lstrip("/") in repo_files
                    ]
                    found_in_code = False
                    for pfile in port_ev_files:
                        content = await _get_file_text(pfile)
                        if str(port) in content:
                            found_in_code = True
                            break
                    if not found_in_code:
                        comp_issues.append(
                            ValidationIssue(
                                component=comp.name,
                                field="port",
                                message=f"Port {port} does not appear in the cited evidence file(s): {port_ev_files}.",
                                severity=ValidationSeverity.ERROR,
                            )
                        )

            if comp.type in (ComponentType.SERVER, ComponentType.WORKER) and start_cmd is not None:
                if confidence.get("start_cmd", 0.0) < 1.0 and "start_cmd" not in evidenced_fields:
                    comp_issues.append(
                        ValidationIssue(
                            component=comp.name,
                            field="start_cmd",
                            message=f"start_cmd '{start_cmd}' has no valid file evidence citation.",
                            severity=ValidationSeverity.ERROR,
                        )
                    )

            if finalize_unresolved and comp_issues:
                # Demote invalid fields to unknown (confidence 0) and create OpenQuestions
                invalid_fields = {i.field for i in comp_issues if i.severity is ValidationSeverity.ERROR}
                if "port" in invalid_fields:
                    port = None
                    confidence["port"] = 0.0
                    q_key = (comp.name, f"{comp.name}.port")
                    if q_key not in existing_question_keys:
                        new_questions.append(
                            OpenQuestion(
                                component=comp.name,
                                field_path=f"{comp.name}.port",
                                question=f"Which port does component '{comp.name}' listen on?",
                                reason="Could not verify port from repository files.",
                            )
                        )
                        existing_question_keys.add(q_key)

                if "start_cmd" in invalid_fields:
                    start_cmd = None
                    confidence["start_cmd"] = 0.0
                    q_key = (comp.name, f"{comp.name}.start_cmd")
                    if q_key not in existing_question_keys:
                        new_questions.append(
                            OpenQuestion(
                                component=comp.name,
                                field_path=f"{comp.name}.start_cmd",
                                question=f"What command starts component '{comp.name}'?",
                                reason="Could not verify start command from repository files.",
                            )
                        )
                        existing_question_keys.add(q_key)

                if "build_cmd" in invalid_fields:
                    build_cmd = None
                    confidence["build_cmd"] = 0.0

                updated_components.append(
                    replace(
                        comp,
                        port=port,
                        start_cmd=start_cmd,
                        build_cmd=build_cmd,
                        evidence=tuple(valid_evidence),
                        field_confidence=confidence,
                    )
                )
            else:
                updated_components.append(comp)
                issues.extend(comp_issues)

        sanitized_manifest = replace(
            manifest,
            components=tuple(updated_components),
            open_questions=tuple(new_questions),
        )
        has_errors = any(i.severity is ValidationSeverity.ERROR for i in issues)
        return ValidationResult(
            is_valid=not has_errors,
            manifest=sanitized_manifest,
            issues=tuple(issues),
        )
