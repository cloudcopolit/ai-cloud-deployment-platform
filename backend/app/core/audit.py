"""Append-only, hash-chained audit log (ADR-030). Never record secrets here."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditLog


@dataclass(frozen=True)
class RequestInfo:
    ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None


def _entry_hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    body = json.dumps({"prev": prev_hash, **payload}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def record(
    db: Session,
    *,
    team_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: object | None = None,
    actor_user_id: uuid.UUID | None = None,
    plan_hash: str | None = None,
    request: RequestInfo | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one entry. A per-team advisory lock keeps the chain linear under concurrency.
    The caller commits (the entry is part of the caller's transaction)."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"audit:{team_id}"})
    prev = db.scalar(
        select(AuditLog.entry_hash)
        .where(AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    info = request or RequestInfo()
    payload = {
        "team_id": str(team_id),
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "plan_hash": plan_hash,
        "details": details or {},
    }
    entry = AuditLog(
        team_id=team_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=payload["target_id"],
        plan_hash=plan_hash,
        ip=info.ip,
        user_agent=(info.user_agent or "")[:255] or None,
        correlation_id=info.correlation_id,
        details=details or {},
        prev_hash=prev,
        entry_hash=_entry_hash(prev, payload),
        # wall-clock, not now(): entries written in one transaction must stay ordered
        created_at=datetime.now(UTC),
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session, team_id: uuid.UUID) -> bool:
    """Recompute every hash for a team; False if any row was altered or removed."""
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at, AuditLog.id)
    ).all()
    prev: str | None = None
    for row in rows:
        payload = {
            "team_id": str(row.team_id),
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "plan_hash": row.plan_hash,
            "details": row.details or {},
        }
        if row.prev_hash != prev or row.entry_hash != _entry_hash(prev, payload):
            return False
        prev = row.entry_hash
    return True
