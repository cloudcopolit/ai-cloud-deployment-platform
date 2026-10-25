import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Ensure root path is in sys.path so ai package is importable
ROOT_DIR = Path(__file__).resolve().parents[4]
if not (ROOT_DIR / "ai").is_dir():
    ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai.agents.architecture.architect import run_architecture_agent
from app.contracts.ai_contracts import AnalysisReport
from app.core.errors import BadRequest, NotFound
from app.core.permissions import check_team_role
from app.models import (
    Architecture,
    ArchitectureVersion,
    Project,
    Repository,
    RepositoryAnalysis,
    User,
)
from app.modules.architectures.schemas import (
    ArchitectureGenerateRequest,
    ArchitectureRead,
    ArchitectureVersionRead,
)


def _to_version_read(v: ArchitectureVersion) -> ArchitectureVersionRead:
    cost_data = (v.architecture_data or {}).get("cost", {})
    monthly_cost = float(cost_data.get("monthly_total", 0.0))

    return ArchitectureVersionRead(
        id=v.id,
        architecture_id=v.architecture_id,
        version_number=v.version_number,
        source_analysis_id=v.source_analysis_id,
        status=v.status,
        architecture_data=v.architecture_data,
        created_by=v.created_by,
        created_at=v.created_at,
        monthly_cost=monthly_cost,
    )


def generate_architecture_proposal(
    db: Session,
    analysis_id: UUID,
    user: User,
    request: ArchitectureGenerateRequest,
) -> ArchitectureVersionRead:
    analysis = db.get(RepositoryAnalysis, analysis_id)
    if not analysis:
        raise NotFound("Analysis job not found.")

    if analysis.status != "SUCCESS" or not analysis.analysis_data:
        raise BadRequest("Analysis job has not completed successfully.")

    repo = db.get(Repository, analysis.repository_id)
    if not repo:
        raise NotFound("Repository not found.")

    project = db.get(Project, repo.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    # Validate and reconstruct the AnalysisReport
    report = AnalysisReport.model_validate(analysis.analysis_data, strict=False)

    # Synthesize ArchitecturePlan via Architecture Agent
    plan = run_architecture_agent(
        report=report,
        source_analysis_id=analysis.id,
        region=request.region,
    )

    # Look for existing active architecture for this project
    arch_name = request.name or f"{project.name} AWS Architecture"
    arch = db.scalar(
        select(Architecture).where(
            Architecture.project_id == project.id,
            Architecture.status == "ACTIVE",
        )
    )

    if not arch:
        arch = Architecture(
            project_id=project.id,
            name=arch_name,
            status="ACTIVE",
        )
        db.add(arch)
        db.flush()

    # Determine next version number
    max_ver = (
        db.scalar(
            select(func.max(ArchitectureVersion.version_number)).where(
                ArchitectureVersion.architecture_id == arch.id
            )
        )
        or 0
    )
    next_ver = max_ver + 1

    # Mark prior active versions as SUPERSEDED
    if max_ver > 0:
        prior_versions = db.scalars(
            select(ArchitectureVersion).where(
                ArchitectureVersion.architecture_id == arch.id,
                ArchitectureVersion.status.in_(["VALIDATED", "APPROVED"]),
            )
        ).all()
        for pv in prior_versions:
            pv.status = "SUPERSEDED"

    version = ArchitectureVersion(
        architecture_id=arch.id,
        version_number=next_ver,
        source_analysis_id=analysis.id,
        status="VALIDATED",
        architecture_data=plan.model_dump(mode="json"),
        created_by=user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    return _to_version_read(version)


def get_architecture_version(
    db: Session,
    architecture_id: UUID,
    version_number: int,
    user: User,
) -> ArchitectureVersionRead:
    arch = db.get(Architecture, architecture_id)
    if not arch:
        raise NotFound("Architecture not found.")

    project = db.get(Project, arch.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    version = db.scalar(
        select(ArchitectureVersion).where(
            ArchitectureVersion.architecture_id == architecture_id,
            ArchitectureVersion.version_number == version_number,
        )
    )
    if not version:
        raise NotFound(f"Architecture version {version_number} not found.")

    return _to_version_read(version)


def list_project_architectures(
    db: Session,
    project_id: UUID,
    user: User,
) -> list[ArchitectureRead]:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    architectures = db.scalars(
        select(Architecture)
        .where(Architecture.project_id == project_id)
        .order_by(Architecture.created_at.desc())
    ).all()

    result: list[ArchitectureRead] = []
    for arch in architectures:
        ver_count = (
            db.scalar(
                select(func.count())
                .select_from(ArchitectureVersion)
                .where(ArchitectureVersion.architecture_id == arch.id)
            )
            or 0
        )

        latest_v = db.scalar(
            select(ArchitectureVersion)
            .where(ArchitectureVersion.architecture_id == arch.id)
            .order_by(ArchitectureVersion.version_number.desc())
        )

        latest_read = _to_version_read(latest_v) if latest_v else None

        result.append(
            ArchitectureRead(
                id=arch.id,
                project_id=arch.project_id,
                name=arch.name,
                status=arch.status,
                created_at=arch.created_at,
                updated_at=arch.updated_at,
                versions_count=ver_count,
                latest_version=latest_read,
            )
        )

    return result
