from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.core.permissions import check_team_role
from app.models import Plan, Project, Subscription, Team, TeamMember, User
from app.modules.teams.schemas import TeamCreate, TeamMemberRead, TeamRead, TeamUpdate


def list_user_teams(db: Session, user: User) -> list[TeamRead]:
    memberships = db.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all()

    results: list[TeamRead] = []
    for m in memberships:
        team = db.get(Team, m.team_id)
        if not team:
            continue

        member_count = (
            db.scalar(
                select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id)
            )
            or 1
        )

        project_count = (
            db.scalar(
                select(func.count())
                .select_from(Project)
                .where(Project.team_id == team.id, Project.status == "ACTIVE")
            )
            or 0
        )

        sub = db.scalar(
            select(Subscription).where(
                Subscription.team_id == team.id,
                Subscription.status.in_(["ACTIVE", "TRIALING"]),
            )
        )
        plan_code = "FREE"
        if sub:
            plan = db.get(Plan, sub.plan_id)
            if plan:
                plan_code = plan.code

        results.append(
            TeamRead(
                id=team.id,
                name=team.name,
                role=m.role,
                created_at=team.created_at,
                member_count=member_count,
                project_count=project_count,
                plan_code=plan_code,
            )
        )
    return results


def get_team_details(db: Session, team_id: UUID, user: User) -> TeamRead:
    membership = check_team_role(db, user, team_id, "MEMBER")
    team = db.get(Team, team_id)
    if not team:
        raise NotFound("Team not found.")

    member_count = (
        db.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id))
        or 1
    )

    project_count = (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.team_id == team.id, Project.status == "ACTIVE")
        )
        or 0
    )

    sub = db.scalar(
        select(Subscription).where(
            Subscription.team_id == team.id,
            Subscription.status.in_(["ACTIVE", "TRIALING"]),
        )
    )
    plan_code = "FREE"
    if sub:
        plan = db.get(Plan, sub.plan_id)
        if plan:
            plan_code = plan.code

    return TeamRead(
        id=team.id,
        name=team.name,
        role=membership.role,
        created_at=team.created_at,
        member_count=member_count,
        project_count=project_count,
        plan_code=plan_code,
    )


def create_team(db: Session, user: User, data: TeamCreate) -> TeamRead:
    team = Team(name=data.name)
    db.add(team)
    db.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role="OWNER")
    db.add(membership)

    free_plan = db.scalar(select(Plan).where(Plan.code == "FREE"))
    if free_plan:
        now = datetime.now(UTC)
        sub = Subscription(
            team_id=team.id,
            plan_id=free_plan.id,
            status="ACTIVE",
            price_at_subscription=free_plan.monthly_price,
            started_at=now,
            current_period_start=now,
        )
        db.add(sub)

    db.commit()
    db.refresh(team)

    return TeamRead(
        id=team.id,
        name=team.name,
        role="OWNER",
        created_at=team.created_at,
        member_count=1,
        project_count=0,
        plan_code="FREE",
    )


def update_team(db: Session, team_id: UUID, user: User, data: TeamUpdate) -> TeamRead:
    check_team_role(db, user, team_id, "ADMIN")
    team = db.get(Team, team_id)
    if not team:
        raise NotFound("Team not found.")

    team.name = data.name
    db.commit()
    db.refresh(team)

    return get_team_details(db, team_id, user)


def list_team_members(db: Session, team_id: UUID, user: User) -> list[TeamMemberRead]:
    check_team_role(db, user, team_id, "MEMBER")
    memberships = db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)).all()

    result: list[TeamMemberRead] = []
    for m in memberships:
        u = db.get(User, m.user_id)
        if not u:
            continue
        result.append(
            TeamMemberRead(
                user_id=u.id,
                name=u.name,
                email=u.email,
                avatar_url=u.avatar_url,
                role=m.role,
                joined_at=m.joined_at,
            )
        )
    return result
