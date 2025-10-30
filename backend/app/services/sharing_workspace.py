from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

import sqlalchemy as sa
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
        planner_session_id=payload.planner_session_id,
        lifecycle_snapshot=payload.lifecycle_snapshot,
        mitigation_history=payload.mitigation_history,
        replay_checkpoint=payload.replay_checkpoint,
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
            "planner_session_id": str(payload.planner_session_id)
            if payload.planner_session_id
            else None,
            "lifecycle_snapshot": payload.lifecycle_snapshot,
            "mitigation_history": payload.mitigation_history,
            "replay_checkpoint": payload.replay_checkpoint,
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
              "mitigation_history": release.mitigation_history,
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
              "replay_checkpoint": release.replay_checkpoint,
              "lifecycle_snapshot": release.lifecycle_snapshot,
          },
          release=release,
      )
    _notify_release_publication(db, release)


def request_federation_link(
    db: Session,
    repo: models.DNARepository,
    payload: schemas.DNARepositoryFederationLinkCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryFederationLink:
    """Register a pending federation link and emit a governance timeline entry."""

    link = models.DNARepositoryFederationLink(
        repository_id=repo.id,
        external_repository_id=payload.external_repository_id,
        external_organization=payload.external_organization,
        permissions=payload.permissions,
        guardrail_contract=payload.guardrail_contract,
        trust_state="requested",
    )
    db.add(link)
    db.flush()
    _create_timeline_event(
        db,
        repo,
        event_type="federation.link_requested",
        actor_id=actor_id,
        payload={
            "link_id": str(link.id),
            "external_repository_id": link.external_repository_id,
            "external_organization": link.external_organization,
        },
    )
    return link


def record_federation_attestation(
    db: Session,
    link: models.DNARepositoryFederationLink,
    payload: schemas.DNARepositoryFederationAttestationCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryFederationAttestation:
    """Capture a guardrail attestation from a federated partner."""

    release: models.DNARepositoryRelease | None = None
    if payload.release_id:
        release = db.get(models.DNARepositoryRelease, payload.release_id)

    attestation = models.DNARepositoryFederationAttestation(
        link_id=link.id,
        release_id=payload.release_id,
        attestor_organization=payload.attestor_organization,
        attestor_contact=payload.attestor_contact,
        guardrail_summary=payload.guardrail_summary,
        provenance_notes=payload.provenance_notes,
        created_by_id=actor_id,
    )
    link.trust_state = "attested"
    link.last_attested_at = datetime.now(timezone.utc)
    db.add(attestation)
    db.add(link)
    _create_timeline_event(
        db,
        link.repository,
        event_type="federation.attestation_recorded",
        actor_id=actor_id,
        payload={
            "link_id": str(link.id),
            "attestor": attestation.attestor_organization,
            "release_id": str(payload.release_id) if payload.release_id else None,
        },
        release=release,
    )
    return attestation


def request_federation_grant(
    db: Session,
    link: models.DNARepositoryFederationLink,
    payload: schemas.DNARepositoryFederationGrantCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryFederationGrant:
    """Request cross-organization access within a federated workspace."""

    now = datetime.now(timezone.utc)
    grant = models.DNARepositoryFederationGrant(
        link_id=link.id,
        organization=payload.organization,
        permission_tier=payload.permission_tier,
        guardrail_scope=payload.guardrail_scope,
        handshake_state="pending",
        requested_by_id=actor_id,
        created_at=now,
        updated_at=now,
    )
    db.add(grant)
    db.flush()
    _create_timeline_event(
        db,
        link.repository,
        event_type="federation.grant_requested",
        actor_id=actor_id,
        payload={
            "link_id": str(link.id),
            "grant_id": str(grant.id),
            "organization": grant.organization,
            "permission_tier": grant.permission_tier,
        },
    )
    return grant


def record_federation_grant_decision(
    db: Session,
    grant: models.DNARepositoryFederationGrant,
    payload: schemas.DNARepositoryFederationGrantDecision,
    *,
    actor_id: UUID,
) -> models.DNARepositoryFederationGrant:
    """Approve or revoke a federated grant and emit guardrail timeline events."""

    now = datetime.now(timezone.utc)
    if payload.decision == "approve":
        grant.handshake_state = "active"
        grant.approved_by_id = actor_id
        grant.activated_at = now
        grant.revoked_at = None
    else:
        grant.handshake_state = "revoked"
        grant.revoked_at = now
    grant.updated_at = now
    db.add(grant)
    _create_timeline_event(
        db,
        grant.link.repository,
        event_type=(
            "federation.grant_approved"
            if payload.decision == "approve"
            else "federation.grant_revoked"
        ),
        actor_id=actor_id,
        payload={
            "grant_id": str(grant.id),
            "organization": grant.organization,
            "decision": payload.decision,
        },
    )
    return grant


def create_release_channel(
    db: Session,
    repo: models.DNARepository,
    payload: schemas.DNARepositoryReleaseChannelCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryReleaseChannel:
    """Provision a release channel to manage audience-specific publishing."""

    channel = models.DNARepositoryReleaseChannel(
        repository_id=repo.id,
        federation_link_id=payload.federation_link_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        audience_scope=payload.audience_scope,
        guardrail_profile=payload.guardrail_profile,
    )
    db.add(channel)
    db.flush()
    _create_timeline_event(
        db,
        repo,
        event_type="channel.created",
        actor_id=actor_id,
        payload={
            "channel_id": str(channel.id),
            "slug": channel.slug,
            "audience_scope": channel.audience_scope,
        },
    )
    return channel


def publish_release_to_channel(
    db: Session,
    channel: models.DNARepositoryReleaseChannel,
    release: models.DNARepositoryRelease,
    payload: schemas.DNARepositoryReleaseChannelVersionCreate,
    *,
    actor_id: UUID,
) -> models.DNARepositoryReleaseChannelVersion:
    """Link a release to a channel with attestation metadata and sequencing."""

    next_sequence = _next_channel_sequence(db, channel.id)
    grant_id = payload.grant_id
    if grant_id:
        grant = db.get(models.DNARepositoryFederationGrant, grant_id)
        if not grant or grant.link.repository_id != release.repository_id:
            raise ValueError("Grant does not belong to repository")
        if grant.handshake_state != "active":
            raise ValueError("Grant must be active to publish to a channel")
    else:
        grant = None
    version = models.DNARepositoryReleaseChannelVersion(
        channel_id=channel.id,
        release_id=release.id,
        sequence=next_sequence,
        version_label=payload.version_label,
        guardrail_attestation=payload.guardrail_attestation,
        provenance_snapshot=payload.provenance_snapshot,
        mitigation_digest=payload.mitigation_digest,
        grant_id=grant.id if grant else None,
    )
    db.add(version)
    db.flush()
    _create_timeline_event(
        db,
        release.repository,
        event_type="channel.version_published",
        actor_id=actor_id,
        payload={
            "channel_id": str(channel.id),
            "release_id": str(release.id),
            "sequence": next_sequence,
            "grant_id": str(grant.id) if grant else None,
        },
        release=release,
    )
    return version


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


def _next_channel_sequence(db: Session, channel_id: UUID) -> int:
    last_sequence = (
        db.query(sa.func.max(models.DNARepositoryReleaseChannelVersion.sequence))
        .filter(models.DNARepositoryReleaseChannelVersion.channel_id == channel_id)
        .scalar()
    )
    return int(last_sequence or 0) + 1


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
