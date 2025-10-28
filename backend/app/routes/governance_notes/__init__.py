"""Governance coaching note CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ... import models, schemas
from ...analytics.governance import invalidate_governance_analytics_cache
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


def _copy_metadata(meta: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a shallow copy of metadata for mutation safety."""

    # purpose: avoid mutating SQLAlchemy-backed JSON structures in-place
    # inputs: persisted metadata dictionary or None
    # outputs: detached dictionary ready for update operations
    # status: experimental

    if not isinstance(meta, dict):
        return {}
    return dict(meta)


def _record_moderation_transition(
    meta: Dict[str, Any],
    *,
    new_state: str,
    actor_id: UUID | None,
    reason: str | None = None,
) -> Dict[str, Any]:
    """Append a moderation history entry and return updated metadata."""

    # purpose: maintain chronological moderation audit trail for collaboration tooling
    # inputs: metadata dictionary, moderation state change attributes
    # outputs: metadata dictionary including appended moderation history entry
    # status: experimental

    history: list[Dict[str, Any]] = []
    existing_history = meta.get("moderation_history")
    if isinstance(existing_history, list):
        history = list(existing_history)
    entry: Dict[str, Any] = {
        "state": new_state,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "actor_id": str(actor_id) if actor_id else None,
    }
    if reason:
        entry["reason"] = reason
    history.append(entry)
    meta["moderation_history"] = history
    return meta


def _apply_metadata_updates(
    current: Dict[str, Any],
    updates: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Merge metadata updates while preserving moderation history."""

    # purpose: allow incremental metadata enrichment without losing audit timeline
    # inputs: current metadata dict, user-supplied updates
    # outputs: merged metadata dictionary
    # status: experimental

    if not updates:
        return current
    merged = _copy_metadata(current)
    merged.update({key: value for key, value in updates.items() if key != "moderation_history"})
    if "moderation_history" in current and "moderation_history" not in merged:
        merged["moderation_history"] = current["moderation_history"]
    return merged


def _apply_moderation_transition(
    note: models.GovernanceCoachingNote,
    *,
    new_state: str,
    actor: models.User,
    metadata: Dict[str, Any] | None = None,
    reason: str | None = None,
) -> bool:
    """Apply moderation state change and optional metadata updates."""

    # purpose: centralize moderation workflow mutations with audit history
    # inputs: coaching note ORM entity, desired state, acting user, metadata updates
    # outputs: bool indicating whether persistence is required
    # status: experimental

    current_meta = _copy_metadata(note.meta)
    changed = False
    if note.moderation_state != new_state:
        current_meta = _record_moderation_transition(
            current_meta,
            new_state=new_state,
            actor_id=actor.id,
            reason=reason,
        )
        note.moderation_state = new_state
        changed = True
    merged_meta = _apply_metadata_updates(current_meta, metadata)
    if merged_meta != note.meta:
        note.meta = merged_meta
        changed = True
    if changed:
        note.updated_at = datetime.now(timezone.utc)
    return changed


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
    sanitized_meta = _copy_metadata(note.meta)
    history = sanitized_meta.pop("moderation_history", [])
    payload = schemas.GovernanceCoachingNoteOut.model_validate(note)
    normalized_history = (
        history if isinstance(history, list) else []
    )
    return payload.model_copy(
        update={
            "reply_count": reply_count,
            "actor": actor_summary,
            "metadata": sanitized_meta,
            "moderation_history": normalized_history,
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

    metadata = _copy_metadata(payload.metadata)
    metadata = _record_moderation_transition(
        metadata,
        new_state="published",
        actor_id=user.id,
        reason=None,
    )

    note = models.GovernanceCoachingNote(
        override_id=override.id,
        baseline_id=payload.baseline_id or override.baseline_id,
        execution_id=payload.execution_id or override.execution_id,
        parent_id=payload.parent_id,
        thread_root_id=thread_root_id,
        author_id=user.id,
        body=body,
        moderation_state="published",
        meta=metadata,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(note)
    db.flush()
    if note.thread_root_id is None:
        note.thread_root_id = note.id
    db.commit()
    db.refresh(note)

    execution_scope: set[UUID] = set()
    for candidate in (note.execution_id, override.execution_id):
        if candidate:
            execution_scope.add(candidate)
    if execution_scope:
        invalidate_governance_analytics_cache(execution_scope)

    reply_counts = _thread_reply_counts(db, note.override_id, {note.thread_root_id})
    return _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))


def _load_note_with_context(db: Session, note_id: UUID) -> models.GovernanceCoachingNote:
    """Load coaching note with override relationships or raise 404."""

    # purpose: share note loading logic across moderation endpoints
    # inputs: database session and note identifier
    # outputs: GovernanceCoachingNote with author, override, baseline, execution eager loaded
    # status: experimental

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
    return note


def _note_response_after_mutation(
    db: Session,
    note: models.GovernanceCoachingNote,
    override: models.GovernanceOverrideAction,
) -> schemas.GovernanceCoachingNoteOut:
    """Invalidate caches, compute reply counts, and serialize note."""

    # purpose: centralize post-mutation cache invalidation and serialization
    # inputs: db session, mutated note, associated override
    # outputs: GovernanceCoachingNoteOut payload with refreshed counts
    # status: experimental

    execution_scope: set[UUID] = set()
    for candidate in (note.execution_id, override.execution_id):
        if candidate:
            execution_scope.add(candidate)
    if execution_scope:
        invalidate_governance_analytics_cache(execution_scope)

    reply_counts = _thread_reply_counts(db, note.override_id, {note.thread_root_id})
    return _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))


def _apply_moderation_action(
    db: Session,
    note: models.GovernanceCoachingNote,
    override: models.GovernanceOverrideAction,
    *,
    actor: models.User,
    new_state: str,
    payload: schemas.GovernanceCoachingNoteModerationAction | None,
) -> schemas.GovernanceCoachingNoteOut:
    """Execute a moderation transition and return serialized response."""

    # purpose: consolidate moderation endpoint behavior with consistent side effects
    # inputs: db session, coaching note entity, override context, acting user, desired state, payload
    # outputs: serialized coaching note reflecting moderation outcome
    # status: experimental

    metadata_updates = None
    reason = None
    if payload is not None:
        metadata_updates = payload.metadata
        reason = payload.reason

    changed = _apply_moderation_transition(
        note,
        new_state=new_state,
        actor=actor,
        metadata=metadata_updates,
        reason=reason,
    )

    if not changed:
        reply_counts = _thread_reply_counts(db, note.override_id, {note.thread_root_id})
        return _serialize_note(note, reply_counts.get(note.thread_root_id or note.id, 0))

    db.add(note)
    db.commit()
    db.refresh(note)

    return _note_response_after_mutation(db, note, override)


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

    note = _load_note_with_context(db, note_id)

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
    metadata_updates = payload.metadata if payload.metadata is not None else None
    if payload.moderation_state is not None or metadata_updates is not None:
        target_state = payload.moderation_state or note.moderation_state
        if target_state is None:
            target_state = note.moderation_state
        moderation_changed = _apply_moderation_transition(
            note,
            new_state=target_state,
            actor=user,
            metadata=metadata_updates,
        )
        changed = changed or moderation_changed

    if not changed:
        return _serialize_note(note, _thread_reply_counts(db, note.override_id, {note.thread_root_id}).get(note.thread_root_id or note.id, 0))

    db.add(note)
    db.commit()
    db.refresh(note)

    return _note_response_after_mutation(db, note, override)


@router.patch(
    "/coaching-notes/{note_id}/flag",
    response_model=schemas.GovernanceCoachingNoteOut,
)
def flag_coaching_note(
    note_id: UUID,
    payload: schemas.GovernanceCoachingNoteModerationAction = Body(
        default_factory=schemas.GovernanceCoachingNoteModerationAction
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Flag a coaching note for review."""

    note = _load_note_with_context(db, note_id)
    override = note.override or _load_override(db, note.override_id)
    _ensure_override_access(db, user, override)

    return _apply_moderation_action(
        db,
        note,
        override,
        actor=user,
        new_state="flagged",
        payload=payload,
    )


@router.patch(
    "/coaching-notes/{note_id}/resolve",
    response_model=schemas.GovernanceCoachingNoteOut,
)
def resolve_coaching_note(
    note_id: UUID,
    payload: schemas.GovernanceCoachingNoteModerationAction = Body(
        default_factory=schemas.GovernanceCoachingNoteModerationAction
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Mark a coaching note thread as resolved."""

    note = _load_note_with_context(db, note_id)
    override = note.override or _load_override(db, note.override_id)
    _ensure_override_access(db, user, override)

    return _apply_moderation_action(
        db,
        note,
        override,
        actor=user,
        new_state="resolved",
        payload=payload,
    )


@router.patch(
    "/coaching-notes/{note_id}/remove",
    response_model=schemas.GovernanceCoachingNoteOut,
)
def remove_coaching_note(
    note_id: UUID,
    payload: schemas.GovernanceCoachingNoteModerationAction = Body(
        default_factory=schemas.GovernanceCoachingNoteModerationAction
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Remove a coaching note from collaborative visibility."""

    note = _load_note_with_context(db, note_id)
    override = note.override or _load_override(db, note.override_id)
    _ensure_override_access(db, user, override)

    return _apply_moderation_action(
        db,
        note,
        override,
        actor=user,
        new_state="removed",
        payload=payload,
    )
