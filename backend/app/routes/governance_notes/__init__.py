"""Governance coaching note CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ... import models, schemas
from ...auth import get_current_user
from ...database import get_db


router = APIRouter(prefix="/api/governance", tags=["governance"])


def _load_override(
    db: Session,
    override_id: UUID,
) -> models.GovernanceOverrideAction:
    """Return override with relationships or raise 404."""

    # purpose: hydrate override context for coaching note operations
    # inputs: database session, override identifier
    # outputs: GovernanceOverrideAction with execution and baseline eager loads
    # status: experimental

    override = (
        db.query(models.GovernanceOverrideAction)
        .options(
            joinedload(models.GovernanceOverrideAction.execution).joinedload(
                models.ProtocolExecution.template
            ),
            joinedload(models.GovernanceOverrideAction.baseline),
        )
        .filter(models.GovernanceOverrideAction.id == override_id)
        .first()
    )
    if not override:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    return override


def _ensure_override_access(
    db: Session,
    user: models.User,
    override: models.GovernanceOverrideAction,
) -> None:
    """Guard override operations with RBAC-aware visibility checks."""

    # purpose: enforce governance RBAC ladder for coaching note collaboration
    # inputs: database session, authenticated user, override record
    # outputs: raises HTTPException when user lacks access
    # status: experimental

    if user.is_admin:
        return
    if override.actor_id == user.id or override.target_reviewer_id == user.id:
        return
    if override.execution is not None and override.execution.run_by == user.id:
        return

    candidate_team_ids: set[UUID] = set()
    if override.baseline and override.baseline.team_id:
        candidate_team_ids.add(override.baseline.team_id)
    template = override.execution.template if override.execution else None
    if template and template.team_id:
        candidate_team_ids.add(template.team_id)

    if not candidate_team_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Override not accessible")

    membership_count = (
        db.query(models.TeamMember)
        .filter(
            models.TeamMember.user_id == user.id,
            models.TeamMember.team_id.in_(list(candidate_team_ids)),
        )
        .count()
    )
    if membership_count == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Override not accessible")


def _thread_reply_counts(
    db: Session,
    override_id: UUID,
    roots: set[UUID] | None = None,
) -> dict[UUID, int]:
    """Return reply counts per thread root for an override."""

    # purpose: aggregate coaching thread sizes for response hydration
    # inputs: override identifier, optional subset of root identifiers
    # outputs: mapping of thread root id to reply count (excluding root node)
    # status: experimental

    query = (
        db.query(
            models.GovernanceCoachingNote.thread_root_id,
            func.count(models.GovernanceCoachingNote.id),
        )
        .filter(models.GovernanceCoachingNote.override_id == override_id)
        .group_by(models.GovernanceCoachingNote.thread_root_id)
    )
    if roots:
        query = query.filter(models.GovernanceCoachingNote.thread_root_id.in_(list(roots)))
    counts: dict[UUID, int] = {}
    for root_id, total in query.all():
        if root_id is None:
            continue
        counts[root_id] = max(int(total) - 1, 0)
    return counts


def _serialize_note(
    note: models.GovernanceCoachingNote,
    reply_count: int,
) -> schemas.GovernanceCoachingNoteOut:
    """Normalize ORM coaching note into API schema."""

    # purpose: centralize schema hydration including actor summaries and reply counts
    # inputs: coaching note ORM instance, computed reply count
    # outputs: GovernanceCoachingNoteOut payload
    # status: experimental

    actor = note.author
    actor_summary = (
        schemas.GovernanceActorSummary(
            id=actor.id,
            name=actor.full_name,
            email=actor.email,
        )
        if actor is not None
        else None
    )
    payload = schemas.GovernanceCoachingNoteOut.model_validate(note)
    return payload.model_copy(
        update={
            "reply_count": reply_count,
            "actor": actor_summary,
        }
    )


@router.get(
    "/overrides/{override_id}/coaching-notes",
    response_model=list[schemas.GovernanceCoachingNoteOut],
)
def list_coaching_notes(
    override_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return ordered coaching notes for a governance override."""

    override = _load_override(db, override_id)
    _ensure_override_access(db, user, override)

    notes = (
        db.query(models.GovernanceCoachingNote)
        .options(joinedload(models.GovernanceCoachingNote.author))
        .filter(models.GovernanceCoachingNote.override_id == override.id)
        .order_by(
            models.GovernanceCoachingNote.created_at.asc(),
            models.GovernanceCoachingNote.id.asc(),
        )
        .all()
    )
    reply_counts = _thread_reply_counts(db, override.id)
    return [
        _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))
        for note in notes
    ]


@router.post(
    "/overrides/{override_id}/coaching-notes",
    response_model=schemas.GovernanceCoachingNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_coaching_note(
    override_id: UUID,
    payload: schemas.GovernanceCoachingNoteCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a new coaching note for the supplied override."""

    override = _load_override(db, override_id)
    _ensure_override_access(db, user, override)

    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body cannot be empty")

    parent: models.GovernanceCoachingNote | None = None
    if payload.parent_id:
        parent = db.get(models.GovernanceCoachingNote, payload.parent_id)
        if not parent or parent.override_id != override.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent note not found")

    thread_root_id = None
    if parent is not None:
        thread_root_id = parent.thread_root_id or parent.id

    note = models.GovernanceCoachingNote(
        override_id=override.id,
        baseline_id=payload.baseline_id or override.baseline_id,
        execution_id=payload.execution_id or override.execution_id,
        parent_id=payload.parent_id,
        thread_root_id=thread_root_id,
        author_id=user.id,
        body=body,
        moderation_state="published",
        meta=payload.metadata or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.flush()
    if note.thread_root_id is None:
        note.thread_root_id = note.id
    db.commit()
    db.refresh(note)

    reply_counts = _thread_reply_counts(db, note.override_id, {note.thread_root_id})
    return _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))


@router.patch(
    "/coaching-notes/{note_id}",
    response_model=schemas.GovernanceCoachingNoteOut,
)
def update_coaching_note(
    note_id: UUID,
    payload: schemas.GovernanceCoachingNoteUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update coaching note body, metadata, or moderation state."""

    note = (
        db.query(models.GovernanceCoachingNote)
        .options(
            joinedload(models.GovernanceCoachingNote.author),
            joinedload(models.GovernanceCoachingNote.override)
            .joinedload(models.GovernanceOverrideAction.execution)
            .joinedload(models.ProtocolExecution.template),
            joinedload(models.GovernanceCoachingNote.override).joinedload(
                models.GovernanceOverrideAction.baseline
            ),
        )
        .filter(models.GovernanceCoachingNote.id == note_id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    override = note.override or _load_override(db, note.override_id)
    _ensure_override_access(db, user, override)

    changed = False
    if payload.body is not None:
        body = payload.body.strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Body cannot be empty")
        if body != note.body:
            note.body = body
            note.last_edited_at = datetime.now(timezone.utc)
            changed = True
    if payload.moderation_state is not None and payload.moderation_state != note.moderation_state:
        note.moderation_state = payload.moderation_state
        changed = True
    if payload.metadata is not None:
        note.meta = payload.metadata
        changed = True

    if not changed:
        return _serialize_note(note, _thread_reply_counts(db, note.override_id, {note.thread_root_id}).get(note.thread_root_id or note.id, 0))

    note.updated_at = datetime.now(timezone.utc)
    db.add(note)
    db.commit()
    db.refresh(note)

    reply_counts = _thread_reply_counts(db, note.override_id, {note.thread_root_id})
    return _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))
