from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models, notify, schemas

# purpose: orchestrate guarded DNA sharing workspace flows with guardrail enforcement
# status: experimental
# depends_on: backend.app.models (DNARepository, DNARepositoryRelease, DNARepositoryReleaseApproval)
# related_docs: docs/sharing/README.md


def create_repository(
    db: Session,
    payload: schemas.DNARepositoryCreate,
    *,
    owner_id: UUID,
) -> models.DNARepository:
    """Persist a guarded DNA repository with initial guardrail policy."""

    repo = models.DNARepository(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        guardrail_policy=payload.guardrail_policy.model_dump(),
        owner_id=owner_id,
        team_id=payload.team_id,
    )
    db.add(repo)
    db.flush()
    _create_timeline_event(
        db,
        repo,
        event_type="repository.created",
        actor_id=owner_id,
        payload={
            "name": repo.name,
            "slug": repo.slug,
            "policy": repo.guardrail_policy,
        },
    )
    return repo


def update_repository(
    db: Session,
    repo: models.DNARepository,
    payload: schemas.DNARepositoryUpdate,
    *,
    actor_id: UUID,
) -> models.DNARepository:
    """Mutate repository metadata and guardrail policy."""

    if payload.name is not None:
        repo.name = payload.name
    if payload.description is not None:
        repo.description = payload.description
    if payload.team_id is not None:
        repo.team_id = payload.team_id
    if payload.guardrail_policy is not None:
        repo.guardrail_policy = payload.guardrail_policy.model_dump()
    repo.updated_at = datetime.now(timezone.utc)
    db.add(repo)
    _create_timeline_event(
        db,
        repo,
        event_type="repository.updated",
        actor_id=actor_id,
        payload={
            "name": repo.name,
            "team_id": str(repo.team_id) if repo.team_id else None,
            "policy": repo.guardrail_policy,
        },
    )
    return repo


def add_collaborator(
    db: Session,
    repo: models.DNARepository,
    *,
    user_id: UUID,
    role: str,
    actor_id: UUID,
) -> models.DNARepositoryCollaborator:
    """Attach a collaborator to a repository and emit a timeline event."""

    collaborator = models.DNARepositoryCollaborator(
        repository_id=repo.id,
        user_id=user_id,
        role=role,
        invitation_status="active",
        meta={},
    )
    db.add(collaborator)
    db.flush()
    _create_timeline_event(
        db,
        repo,
        event_type="repository.collaborator_added",
        actor_id=actor_id,
        payload={
            "collaborator_id": str(collaborator.user_id),
            "role": collaborator.role,
        },
    )
    return collaborator


def create_release(
    db: Session,
    repo: models.DNARepository,
    payload: schemas.DNARepositoryReleaseCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryRelease:
    """Create a guarded release enforcing repository policy."""

    guardrail_state = _evaluate_guardrail_snapshot(repo, payload.guardrail_snapshot, payload.planner_session_id)
    status = "awaiting_approval" if guardrail_state == "cleared" else "requires_mitigation"

    release = models.DNARepositoryRelease(
        repository_id=repo.id,
        version=payload.version,
        title=payload.title,
        notes=payload.notes,
        created_by_id=actor_id,
        status=status,
        guardrail_state=guardrail_state,
        guardrail_snapshot=payload.guardrail_snapshot,
        mitigation_summary=payload.mitigation_summary,
    )
    db.add(release)
    db.flush()
    _create_timeline_event(
        db,
        repo,
        event_type="release.created",
        actor_id=actor_id,
        payload={
            "release_id": str(release.id),
            "version": release.version,
            "guardrail_state": release.guardrail_state,
        },
        release=release,
    )
    return release


def record_release_approval(
    db: Session,
    release: models.DNARepositoryRelease,
    *,
    approver_id: UUID,
    approval_payload: schemas.DNARepositoryReleaseApprovalCreate,
) -> models.DNARepositoryRelease:
    """Apply an approval decision and publish if guardrail quota met."""

    approval = (
        db.query(models.DNARepositoryReleaseApproval)
        .filter(models.DNARepositoryReleaseApproval.release_id == release.id)
        .filter(models.DNARepositoryReleaseApproval.approver_id == approver_id)
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if approval is None:
        approval = models.DNARepositoryReleaseApproval(
            release_id=release.id,
            approver_id=approver_id,
            guardrail_flags=approval_payload.guardrail_flags,
            status=approval_payload.status,
            notes=approval_payload.notes,
        )
        db.add(approval)
    else:
        approval.status = approval_payload.status
        approval.guardrail_flags = approval_payload.guardrail_flags
        approval.notes = approval_payload.notes
        approval.updated_at = now
    db.flush()

    _create_timeline_event(
        db,
        release.repository,
        event_type="release.approval_recorded",
        actor_id=approver_id,
        payload={
            "release_id": str(release.id),
            "status": approval.status,
            "guardrail_flags": approval.guardrail_flags,
        },
        release=release,
    )

    if approval_payload.status == "rejected":
        release.status = "rejected"
        release.guardrail_state = "blocked"
        release.updated_at = now
        db.add(release)
        return release

    _maybe_publish_release(db, release)
    return release


def _maybe_publish_release(db: Session, release: models.DNARepositoryRelease) -> None:
    repo = release.repository
    policy = repo.guardrail_policy or {}
    threshold = int(policy.get("approval_threshold", 1))
    approvals: Iterable[models.DNARepositoryReleaseApproval] = (
        approval
        for approval in release.approvals
        if approval.status == "approved"
    )
    approved_count = sum(1 for _ in approvals)
    if approved_count < threshold:
        return
    if release.status == "published":
        return
    now = datetime.now(timezone.utc)
    release.status = "published"
    release.guardrail_state = "cleared"
    release.published_at = now
    release.updated_at = now
    db.add(release)
    _create_timeline_event(
        db,
        repo,
        event_type="release.published",
        actor_id=None,
        payload={
            "release_id": str(release.id),
            "version": release.version,
        },
        release=release,
    )
    _notify_release_publication(db, release)


def _notify_release_publication(db: Session, release: models.DNARepositoryRelease) -> None:
    owner = release.repository.owner
    subject = f"DNA repository release published: {release.repository.name} {release.version}"
    message = (
        f"Release {release.version} for repository {release.repository.name} was published with guardrail state {release.guardrail_state}."
    )
    if owner and owner.email:
        notify.send_email(owner.email, subject, message)
    for collaborator in release.repository.collaborators:
        user = collaborator.user
        if user and user.email:
            notify.send_email(user.email, subject, message)


def _create_timeline_event(
    db: Session,
    repo: models.DNARepository,
    *,
    event_type: str,
    payload: dict,
    actor_id: UUID | None,
    release: models.DNARepositoryRelease | None = None,
) -> models.DNARepositoryTimelineEvent:
    event = models.DNARepositoryTimelineEvent(
        repository_id=repo.id,
        release_id=release.id if release else None,
        event_type=event_type,
        payload=payload,
        created_by_id=actor_id,
    )
    db.add(event)
    db.flush()
    return event


def _evaluate_guardrail_snapshot(
    repo: models.DNARepository,
    snapshot: dict,
    planner_session_id: UUID | None,
) -> str:
    policy = repo.guardrail_policy or {}
    breaches = snapshot.get("breaches") if isinstance(snapshot, dict) else None
    custody_status = snapshot.get("custody_status") if isinstance(snapshot, dict) else None
    if policy.get("requires_planner_link") and not planner_session_id:
        return "missing_planner_link"
    if policy.get("requires_custody_clearance"):
        if custody_status and custody_status not in {"clear", "stable"}:
            return "custody_blocked"
        if breaches:
            return "custody_blocked"
    return "cleared"
