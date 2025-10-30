from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import SessionLocal, get_db
from ..services import sharing_workspace

# purpose: expose guarded DNA sharing workspace APIs with guardrail enforcement
# status: experimental

router = APIRouter(prefix="/api/sharing", tags=["sharing"])


@router.get("/repositories", response_model=List[schemas.DNARepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> List[models.DNARepository]:
    team_ids = [
        membership.team_id
        for membership in user.teams
        if membership.team_id is not None
    ]
    query = (
        db.query(models.DNARepository)
        .options(
            joinedload(models.DNARepository.collaborators),
            joinedload(models.DNARepository.releases).joinedload(models.DNARepositoryRelease.approvals),
            joinedload(models.DNARepository.releases).joinedload(models.DNARepositoryRelease.channel_versions),
            joinedload(models.DNARepository.release_channels).joinedload(models.DNARepositoryReleaseChannel.versions),
            joinedload(models.DNARepository.federation_links)
            .joinedload(models.DNARepositoryFederationLink.attestations),
            joinedload(models.DNARepository.federation_links)
            .joinedload(models.DNARepositoryFederationLink.grants),
        )
        .filter(
            sa.or_(
                models.DNARepository.owner_id == user.id,
                models.DNARepository.collaborators.any(
                    models.DNARepositoryCollaborator.user_id == user.id
                ),
                models.DNARepository.team_id.in_(team_ids) if team_ids else sa.false(),
            )
        )
        .order_by(models.DNARepository.updated_at.desc())
    )
    repositories = query.all()
    return repositories


@router.post("/repositories", response_model=schemas.DNARepositoryOut, status_code=status.HTTP_201_CREATED)
def create_repository(
    payload: schemas.DNARepositoryCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepository:
    existing = (
        db.query(models.DNARepository)
        .filter(sa.func.lower(models.DNARepository.slug) == payload.slug.lower())
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Repository slug already in use")
    repo = sharing_workspace.create_repository(db, payload, owner_id=user.id)
    db.commit()
    db.refresh(repo)
    return repo


@router.patch("/repositories/{repository_id}", response_model=schemas.DNARepositoryOut)
def update_repository(
    repository_id: UUID,
    payload: schemas.DNARepositoryUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepository:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owners can update repositories")
    repo = sharing_workspace.update_repository(db, repo, payload, actor_id=user.id)
    db.commit()
    db.refresh(repo)
    return repo


@router.post("/repositories/{repository_id}/collaborators", response_model=schemas.DNARepositoryCollaboratorOut, status_code=status.HTTP_201_CREATED)
def add_collaborator(
    repository_id: UUID,
    payload: schemas.DNARepositoryCollaboratorAdd,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryCollaborator:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != user.id and user.id != payload.user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions to invite collaborators")
    try:
        collaborator = sharing_workspace.add_collaborator(
            db,
            repo,
            user_id=payload.user_id,
            role=payload.role,
            actor_id=user.id,
        )
        db.commit()
    except IntegrityError as exc:  # pragma: no cover - defensive
        db.rollback()
        raise HTTPException(status_code=400, detail="Collaborator already invited") from exc
    db.refresh(collaborator)
    return collaborator


@router.post(
    "/repositories/{repository_id}/releases",
    response_model=schemas.DNARepositoryReleaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_release(
    repository_id: UUID,
    payload: schemas.DNARepositoryReleaseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryRelease:
    repo = (
        db.query(models.DNARepository)
        .options(joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepository.id == repository_id)
        .one_or_none()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_publish(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create releases")
    try:
        release = sharing_workspace.create_release(db, repo, payload, actor_id=user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Release version already exists") from exc
    db.refresh(release)
    db.refresh(repo)
    return release


@router.post(
    "/releases/{release_id}/approvals",
    response_model=schemas.DNARepositoryReleaseOut,
)
def approve_release(
    release_id: UUID,
    payload: schemas.DNARepositoryReleaseApprovalCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryRelease:
    release = (
        db.query(models.DNARepositoryRelease)
        .options(joinedload(models.DNARepositoryRelease.repository).joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepositoryRelease.id == release_id)
        .one_or_none()
    )
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if not _user_can_approve(user, release.repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to approve releases")
    release = sharing_workspace.record_release_approval(
        db,
        release,
        approver_id=user.id,
        approval_payload=payload,
    )
    db.commit()
    db.refresh(release)
    return release


@router.get(
    "/repositories/{repository_id}/timeline",
    response_model=List[schemas.DNARepositoryTimelineEventOut],
)
def get_timeline(
    repository_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> List[models.DNARepositoryTimelineEvent]:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_view(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view timeline")
    events = (
        db.query(models.DNARepositoryTimelineEvent)
        .filter(models.DNARepositoryTimelineEvent.repository_id == repository_id)
        .order_by(models.DNARepositoryTimelineEvent.created_at.desc())
        .all()
    )
    return events


@router.get(
    "/repositories/{repository_id}/reviews/stream",
    response_class=StreamingResponse,
)
async def stream_repository_reviews(
    repository_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream repository review activity for collaborative sessions."""

    # purpose: broadcast real-time guardrail review events for collaboration hub clients
    # status: experimental
    # depends_on: DNARepositoryTimelineEvent, DNARepositoryReleaseChannelVersion
    repo = (
        db.query(models.DNARepository)
        .options(
            joinedload(models.DNARepository.collaborators),
            joinedload(models.DNARepository.releases)
            .joinedload(models.DNARepositoryRelease.approvals),
            joinedload(models.DNARepository.releases)
            .joinedload(models.DNARepositoryRelease.channel_versions),
            joinedload(models.DNARepository.release_channels)
            .joinedload(models.DNARepositoryReleaseChannel.versions),
            joinedload(models.DNARepository.federation_links)
            .joinedload(models.DNARepositoryFederationLink.attestations),
        )
        .filter(models.DNARepository.id == repository_id)
        .one_or_none()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_view(user, repo):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to join review stream",
        )

    snapshot = _serialize_repository_snapshot(repo)
    last_cursor: datetime | None = None
    last_event_id: UUID | None = None

    async def event_iterator():
        nonlocal last_cursor, last_event_id
        keepalive_at = datetime.now(timezone.utc)
        initial_payload = {
            "type": "snapshot",
            "repository": snapshot,
            "generated_at": _isoformat(datetime.now(timezone.utc)),
        }
        yield _render_sse_payload(initial_payload)

        while True:
            if await request.is_disconnected():
                break

            batch = await asyncio.to_thread(
                _load_review_events,
                repository_id,
                last_cursor,
                last_event_id,
            )
            if batch:
                for item, created_at, event_id in batch:
                    item["generated_at"] = _isoformat(datetime.now(timezone.utc))
                    yield _render_sse_payload(item)
                    last_cursor = created_at
                    last_event_id = event_id
                keepalive_at = datetime.now(timezone.utc)
            else:
                now = datetime.now(timezone.utc)
                if (now - keepalive_at).total_seconds() >= 15:
                    yield ": keep-alive\n\n"
                    keepalive_at = now
                await asyncio.sleep(1.0)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(event_iterator(), media_type="text/event-stream", headers=headers)


@router.post(
    "/repositories/{repository_id}/federation/links",
    response_model=schemas.DNARepositoryFederationLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def request_federation_link(
    repository_id: UUID,
    payload: schemas.DNARepositoryFederationLinkCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryFederationLink:
    repo = (
        db.query(models.DNARepository)
        .options(joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepository.id == repository_id)
        .one_or_none()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_publish(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to federate repository")
    link = sharing_workspace.request_federation_link(
        db,
        repo,
        payload,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(link)
    return link


@router.post(
    "/federation/links/{link_id}/attestations",
    response_model=schemas.DNARepositoryFederationAttestationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_federation_attestation(
    link_id: UUID,
    payload: schemas.DNARepositoryFederationAttestationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryFederationAttestation:
    link = (
        db.query(models.DNARepositoryFederationLink)
        .options(
            joinedload(models.DNARepositoryFederationLink.repository)
            .joinedload(models.DNARepository.collaborators),
            joinedload(models.DNARepositoryFederationLink.repository)
            .joinedload(models.DNARepository.releases),
        )
        .filter(models.DNARepositoryFederationLink.id == link_id)
        .one_or_none()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Federation link not found")
    if not _user_can_publish(user, link.repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to record attestation")
    attestation = sharing_workspace.record_federation_attestation(
        db,
        link,
        payload,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(attestation)
    db.refresh(link)
    return attestation


@router.post(
    "/federation/links/{link_id}/grants",
    response_model=schemas.DNARepositoryFederationGrantOut,
    status_code=status.HTTP_201_CREATED,
)
def request_federation_grant(
    link_id: UUID,
    payload: schemas.DNARepositoryFederationGrantCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryFederationGrant:
    link = (
        db.query(models.DNARepositoryFederationLink)
        .options(joinedload(models.DNARepositoryFederationLink.repository).joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepositoryFederationLink.id == link_id)
        .one_or_none()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Federation link not found")
    if not _user_can_publish(user, link.repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to request grant")
    grant = sharing_workspace.request_federation_grant(
        db,
        link,
        payload,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.post(
    "/federation/grants/{grant_id}/decision",
    response_model=schemas.DNARepositoryFederationGrantOut,
)
def decide_federation_grant(
    grant_id: UUID,
    payload: schemas.DNARepositoryFederationGrantDecision,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryFederationGrant:
    grant = (
        db.query(models.DNARepositoryFederationGrant)
        .options(
            joinedload(models.DNARepositoryFederationGrant.link)
            .joinedload(models.DNARepositoryFederationLink.repository)
            .joinedload(models.DNARepository.collaborators)
        )
        .filter(models.DNARepositoryFederationGrant.id == grant_id)
        .one_or_none()
    )
    if not grant:
        raise HTTPException(status_code=404, detail="Federation grant not found")
    repository = grant.link.repository
    if not _user_can_publish(user, repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to decide grant")
    grant = sharing_workspace.record_federation_grant_decision(
        db,
        grant,
        payload,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(grant)
    return grant


@router.post(
    "/repositories/{repository_id}/channels",
    response_model=schemas.DNARepositoryReleaseChannelOut,
    status_code=status.HTTP_201_CREATED,
)
def create_release_channel(
    repository_id: UUID,
    payload: schemas.DNARepositoryReleaseChannelCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryReleaseChannel:
    repo = (
        db.query(models.DNARepository)
        .options(joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepository.id == repository_id)
        .one_or_none()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_publish(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create release channel")
    channel = sharing_workspace.create_release_channel(
        db,
        repo,
        payload,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.post(
    "/channels/{channel_id}/versions",
    response_model=schemas.DNARepositoryReleaseChannelVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def publish_release_to_channel(
    channel_id: UUID,
    payload: schemas.DNARepositoryReleaseChannelVersionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryReleaseChannelVersion:
    channel = (
        db.query(models.DNARepositoryReleaseChannel)
        .options(joinedload(models.DNARepositoryReleaseChannel.repository).joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepositoryReleaseChannel.id == channel_id)
        .one_or_none()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Release channel not found")
    if not _user_can_publish(user, channel.repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to publish release to channel")
    release = db.get(models.DNARepositoryRelease, payload.release_id)
    if not release or release.repository_id != channel.repository_id:
        raise HTTPException(status_code=404, detail="Release not found for repository")
    try:
        version = sharing_workspace.publish_release_to_channel(
            db,
            channel,
            release,
            payload,
            actor_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(version)
    return version


def _user_can_view(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    if any(collab.user_id == user.id for collab in repo.collaborators):
        return True
    return bool(
        repo.team_id
        and any(team.team_id == repo.team_id for team in user.teams)
    )


def _user_can_publish(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    return any(
        collab.user_id == user.id and collab.role in {"maintainer", "owner"}
        for collab in repo.collaborators
    )


def _user_can_approve(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    return any(
        collab.user_id == user.id and collab.role in {"maintainer", "owner"}
        for collab in repo.collaborators
    )


def _load_review_events(
    repository_id: UUID,
    last_cursor: datetime | None,
    last_event_id: UUID | None,
) -> list[tuple[dict, datetime, UUID]]:
    session = SessionLocal()
    try:
        query = (
            session.query(models.DNARepositoryTimelineEvent)
            .filter(models.DNARepositoryTimelineEvent.repository_id == repository_id)
        )
        if last_cursor is not None:
            query = query.filter(
                sa.or_(
                    models.DNARepositoryTimelineEvent.created_at > last_cursor,
                    sa.and_(
                        models.DNARepositoryTimelineEvent.created_at == last_cursor,
                        models.DNARepositoryTimelineEvent.id != last_event_id,
                    ),
                )
            )
        events = (
            query.order_by(
                models.DNARepositoryTimelineEvent.created_at.asc(),
                models.DNARepositoryTimelineEvent.id.asc(),
            ).all()
        )
        release_cache: dict[UUID, dict | None] = {}
        link_cache: dict[UUID, dict | None] = {}
        channel_cache: dict[UUID, dict | None] = {}
        grant_cache: dict[UUID, dict | None] = {}
        batch: list[tuple[dict, datetime, UUID]] = []
        for event in events:
            payload = _serialize_timeline_event(event)
            if event.release_id:
                release_data = release_cache.get(event.release_id)
                if release_data is None and event.release_id not in release_cache:
                    release = (
                        session.query(models.DNARepositoryRelease)
                        .options(
                            joinedload(models.DNARepositoryRelease.approvals),
                            joinedload(models.DNARepositoryRelease.channel_versions)
                            .joinedload(models.DNARepositoryReleaseChannelVersion.channel),
                        )
                        .filter(models.DNARepositoryRelease.id == event.release_id)
                        .one_or_none()
                    )
                    release_data = (
                        schemas.DNARepositoryReleaseOut.model_validate(release).model_dump(mode="json")
                        if release
                        else None
                    )
                    release_cache[event.release_id] = release_data
                if release_cache.get(event.release_id):
                    payload["release"] = release_cache[event.release_id]
            payload_map = payload.get("payload") if isinstance(payload.get("payload"), dict) else None
            link_id = payload_map.get("link_id") if payload_map else None
            if link_id:
                try:
                    link_uuid = UUID(link_id)
                except (TypeError, ValueError):
                    link_uuid = None
                if link_uuid:
                    link_data = link_cache.get(link_uuid)
                    if link_data is None and link_uuid not in link_cache:
                        link = (
                            session.query(models.DNARepositoryFederationLink)
                            .options(joinedload(models.DNARepositoryFederationLink.attestations))
                            .filter(models.DNARepositoryFederationLink.id == link_uuid)
                            .one_or_none()
                        )
                        link_data = (
                            schemas.DNARepositoryFederationLinkOut.model_validate(link).model_dump(mode="json")
                            if link
                            else None
                        )
                        link_cache[link_uuid] = link_data
                    if link_cache.get(link_uuid):
                        payload["federation_link"] = link_cache[link_uuid]
            channel_id = payload_map.get("channel_id") if payload_map else None
            if channel_id:
                try:
                    channel_uuid = UUID(channel_id)
                except (TypeError, ValueError):
                    channel_uuid = None
                if channel_uuid:
                    channel_data = channel_cache.get(channel_uuid)
                    if channel_data is None and channel_uuid not in channel_cache:
                        channel = (
                            session.query(models.DNARepositoryReleaseChannel)
                            .options(joinedload(models.DNARepositoryReleaseChannel.versions))
                            .filter(models.DNARepositoryReleaseChannel.id == channel_uuid)
                            .one_or_none()
                        )
                        channel_data = (
                            schemas.DNARepositoryReleaseChannelOut.model_validate(channel).model_dump(mode="json")
                            if channel
                            else None
                        )
                        channel_cache[channel_uuid] = channel_data
                    if channel_cache.get(channel_uuid):
                        payload["release_channel"] = channel_cache[channel_uuid]
            grant_id = payload_map.get("grant_id") if payload_map else None
            if grant_id:
                try:
                    grant_uuid = UUID(grant_id)
                except (TypeError, ValueError):
                    grant_uuid = None
                if grant_uuid:
                    grant_data = grant_cache.get(grant_uuid)
                    if grant_data is None and grant_uuid not in grant_cache:
                        grant = (
                            session.query(models.DNARepositoryFederationGrant)
                            .filter(models.DNARepositoryFederationGrant.id == grant_uuid)
                            .one_or_none()
                        )
                        grant_data = (
                            schemas.DNARepositoryFederationGrantOut.model_validate(grant).model_dump(mode="json")
                            if grant
                            else None
                        )
                        grant_cache[grant_uuid] = grant_data
                    if grant_cache.get(grant_uuid):
                        payload["federation_grant"] = grant_cache[grant_uuid]
            payload["type"] = "timeline"
            batch.append((payload, event.created_at, event.id))
        return batch
    finally:
        session.close()


def _serialize_repository_snapshot(repo: models.DNARepository) -> dict:
    return schemas.DNARepositoryOut.model_validate(repo).model_dump(mode="json")


def _serialize_timeline_event(event: models.DNARepositoryTimelineEvent) -> dict:
    return {
        "id": str(event.id),
        "repository_id": str(event.repository_id),
        "release_id": str(event.release_id) if event.release_id else None,
        "event_type": event.event_type,
        "payload": event.payload or {},
        "created_at": _isoformat(event.created_at),
        "created_by_id": str(event.created_by_id) if event.created_by_id else None,
    }


def _render_sse_payload(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()
