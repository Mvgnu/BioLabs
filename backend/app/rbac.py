from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models

# purpose: centralize RBAC helpers for governance override workflows
# status: pilot


@dataclass(frozen=True)
class OverrideEscalationTier:
    """Describe the actor's governance escalation tier."""

    # purpose: carry escalation metadata for override reversal decisions
    key: str
    label: str
    level: int
    scope: str | None = None
    team_id: UUID | None = None


_TEAM_ROLE_LEVELS: dict[str, int] = {
    "observer": 10,
    "member": 20,
    "reviewer": 30,
    "lead": 50,
    "manager": 60,
    "owner": 70,
}

_DIRECT_OVERRIDE_LEVELS: dict[str, tuple[str, int]] = {
    "override_actor": ("override_actor", 80),
    "target_reviewer": ("target_reviewer", 65),
    "execution_runner": ("execution_runner", 55),
}

_REVERSAL_MIN_LEVEL: dict[str, int] = {
    "reassign": 30,
    "cooldown": 50,
    "escalate": 60,
}


def describe_level(level: int) -> str:
    """Return a human-readable description for a tier level."""

    ladder = sorted({**_TEAM_ROLE_LEVELS, "override_actor": 80, "admin": 100}.items(), key=lambda item: item[1])
    label = next((name for name, value in ladder if value == level), None)
    return label or f"tier_{level}"


def required_reversal_level(action: str) -> int:
    """Return the minimum escalation level required to reverse an action."""

    return _REVERSAL_MIN_LEVEL.get(action, 30)


def resolve_override_escalation_tier(
    db: Session,
    *,
    user: models.User,
    override: models.GovernanceOverrideAction,
) -> OverrideEscalationTier | None:
    """Compute the actor's escalation tier for the supplied override."""

    if user.is_admin:
        return OverrideEscalationTier(
            key="platform_admin",
            label="admin",
            level=100,
            scope="global",
        )

    if override.actor_id == user.id:
        direct_key, level = _DIRECT_OVERRIDE_LEVELS["override_actor"]
        return OverrideEscalationTier(key=direct_key, label="override_actor", level=level, scope="override")
    if override.target_reviewer_id and override.target_reviewer_id == user.id:
        direct_key, level = _DIRECT_OVERRIDE_LEVELS["target_reviewer"]
        return OverrideEscalationTier(key=direct_key, label="target_reviewer", level=level, scope="override")
    if override.execution is not None and override.execution.run_by == user.id:
        direct_key, level = _DIRECT_OVERRIDE_LEVELS["execution_runner"]
        return OverrideEscalationTier(key=direct_key, label="execution_runner", level=level, scope="execution")

    candidate_team_ids: set[UUID] = set()
    if override.baseline and override.baseline.team_id:
        candidate_team_ids.add(override.baseline.team_id)
    template = override.execution.template if override.execution else None
    if template and template.team_id:
        candidate_team_ids.add(template.team_id)

    if not candidate_team_ids:
        return None

    memberships = (
        db.query(models.TeamMember)
        .filter(models.TeamMember.user_id == user.id, models.TeamMember.team_id.in_(list(candidate_team_ids)))
        .all()
    )
    best: OverrideEscalationTier | None = None
    for membership in memberships:
        role = (membership.role or "member").lower()
        level = _TEAM_ROLE_LEVELS.get(role, 20)
        candidate = OverrideEscalationTier(
            key=f"team:{role}",
            label=role,
            level=level,
            scope=f"team:{membership.team_id}",
            team_id=membership.team_id,
        )
        if best is None or candidate.level > best.level:
            best = candidate
    return best


def check_team_role(db: Session, user: models.User, team_id: UUID, roles: list[str] | tuple[str, ...]):
    if user.is_admin:
        return
    membership = (
        db.query(models.TeamMember)
        .filter(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user.id)
        .first()
    )
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Not authorized")


def ensure_project_member(db: Session, user: models.User, project_id: UUID, roles: list[str] | tuple[str, ...] = ("member", "owner")):
    if user.is_admin:
        return
    membership = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project_id, models.ProjectMember.user_id == user.id)
        .first()
    )
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Not authorized")


def ensure_item_access(
    db: Session,
    user: models.User,
    item_id: UUID,
    roles: list[str] | tuple[str, ...] = ("member", "manager", "owner"),
) -> models.InventoryItem:
    """Return the item if the user has access, otherwise raise 403."""
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if user.is_admin or item.owner_id == user.id:
        return item
    if item.team_id:
        membership = (
            db.query(models.TeamMember)
            .filter(models.TeamMember.team_id == item.team_id, models.TeamMember.user_id == user.id)
            .first()
        )
        if membership and membership.role in roles:
            return item
    raise HTTPException(status_code=403, detail="Not authorized")
