from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, QuotaExceeded
from app.core.permissions import check_team_role
from app.models import Plan, Project, Repository, Subscription, Team, TeamMember, User
from app.modules.projects.schemas import ProjectCreate, ProjectRead, ProjectUpdate


def _to_project_read(db: Session, project: Project) -> ProjectRead:
    repo_count = (
        db.scalar(
            select(func.count()).select_from(Repository).where(Repository.project_id == project.id)
        )
        or 0
    )

    team = db.get(Team, project.team_id)
    team_name = team.name if team else None

    return ProjectRead(
        id=project.id,
        team_id=project.team_id,
        team_name=team_name,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        repository_count=repo_count,
        deployment_count=0,
    )


def list_team_projects(
    db: Session, team_id: UUID, user: User, status_filter: str | None = "ACTIVE"
) -> list[ProjectRead]:
    check_team_role(db, user, team_id, "MEMBER")

    query = select(Project).where(Project.team_id == team_id)
    if status_filter:
        query = query.where(Project.status == status_filter)
    query = query.order_by(Project.created_at.desc())

    projects = db.scalars(query).all()
    return [_to_project_read(db, p) for p in projects]


def list_user_projects(
    db: Session, user: User, status_filter: str | None = "ACTIVE"
) -> list[ProjectRead]:
    user_team_ids = select(TeamMember.team_id).where(TeamMember.user_id == user.id)

    query = select(Project).where(Project.team_id.in_(user_team_ids))
    if status_filter:
        query = query.where(Project.status == status_filter)
    query = query.order_by(Project.created_at.desc())

    projects = db.scalars(query).all()
    return [_to_project_read(db, p) for p in projects]


def get_project_details(db: Session, project_id: UUID, user: User) -> ProjectRead:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")
    return _to_project_read(db, project)


def create_project(db: Session, team_id: UUID, user: User, data: ProjectCreate) -> ProjectRead:
    check_team_role(db, user, team_id, "ADMIN")

    # Check subscription plan limits for max_projects
    sub = db.scalar(
        select(Subscription).where(
            Subscription.team_id == team_id,
            Subscription.status.in_(["ACTIVE", "TRIALING"]),
        )
    )
    if sub:
        plan = db.get(Plan, sub.plan_id)
        if plan and plan.limits and "max_projects" in plan.limits:
            max_projects = plan.limits["max_projects"]
            current_active = (
                db.scalar(
                    select(func.count())
                    .select_from(Project)
                    .where(Project.team_id == team_id, Project.status == "ACTIVE")
                )
                or 0
            )
            if current_active >= max_projects:
                plan_name = plan.name if plan else "current"
                raise QuotaExceeded(
                    f"Plan limit: max {max_projects} active project(s) on {plan_name} plan.",
                    details={"limit": max_projects, "current": current_active},
                )

    project = Project(
        team_id=team_id,
        name=data.name,
        description=data.description,
        status="ACTIVE",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return _to_project_read(db, project)


def update_project(db: Session, project_id: UUID, user: User, data: ProjectUpdate) -> ProjectRead:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "ADMIN")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description

    db.commit()
    db.refresh(project)
    return _to_project_read(db, project)


def archive_project(db: Session, project_id: UUID, user: User) -> ProjectRead:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "ADMIN")

    project.status = "ARCHIVED"
    db.commit()
    db.refresh(project)
    return _to_project_read(db, project)
