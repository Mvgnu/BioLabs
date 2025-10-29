"""Cloning planner API routes."""

# purpose: expose cloning planner session orchestration endpoints
# status: experimental
# depends_on: backend.app.services.cloning_planner, backend.app.schemas

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, pubsub
from ..auth import get_current_user
from ..database import get_db
from ..services import cloning_planner
from ..tasks import celery_app
from ..rbac import check_team_role

router = APIRouter(prefix="/api/cloning-planner", tags=["cloning-planner"])


@router.post("/sessions", response_model=schemas.CloningPlannerSessionOut, status_code=status.HTTP_201_CREATED)
def create_cloning_planner_session(
    payload: schemas.CloningPlannerSessionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Create a new cloning planner session."""

    # purpose: allow operators to bootstrap cloning planner workflows via API
    planner = cloning_planner.create_session(
        db,
        created_by=user,
        assembly_strategy=payload.assembly_strategy,
        input_sequences=[sequence.model_dump() for sequence in payload.input_sequences],
        protocol_execution_id=payload.protocol_execution_id,
        metadata=payload.metadata or {},
        toolkit_preset=payload.toolkit_preset,
    )
    db.commit()
    db.refresh(planner)
    cloning_planner.enqueue_pipeline(
        planner.id,
        preset_id=payload.toolkit_preset,
    )
    db.refresh(planner)
    serialised = cloning_planner.serialize_session(planner)
    return schemas.CloningPlannerSessionOut(**serialised)


@router.get("/sessions/{session_id}", response_model=schemas.CloningPlannerSessionOut)
def get_cloning_planner_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Fetch a cloning planner session by identifier."""

    # purpose: retrieve planner progress for dashboards and wizard resume flows
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(planner))


@router.get(
    "/sessions/{session_id}/guardrails",
    response_model=schemas.CloningPlannerGuardrailStatus,
)
def get_cloning_planner_guardrails(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerGuardrailStatus:
    """Return custody-aware guardrail status for a planner session."""

    planner = (
        db.query(models.CloningPlannerSession)
        .options(
            joinedload(models.CloningPlannerSession.protocol_execution).joinedload(
                models.ProtocolExecution.template
            )
        )
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    team_id = None
    if planner.protocol_execution and planner.protocol_execution.template:
        team_id = planner.protocol_execution.template.team_id
    if not user.is_admin:
        if planner.created_by_id not in {None, user.id}:
            if team_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Guardrail status requires governance membership",
                )
            check_team_role(db, user, team_id, ["owner", "manager", "member"])
    snapshot = cloning_planner.guardrail_status_snapshot(db, planner)
    return schemas.CloningPlannerGuardrailStatus(**snapshot)


@router.get("/sessions/{session_id}/events", response_class=StreamingResponse)
async def stream_cloning_planner_events(
    session_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    branch: UUID | None = None,
    since: str | None = None,
    stage: str | None = None,
    gate: str | None = None,
    compare_branch: UUID | None = None,
) -> StreamingResponse:
    """Stream cloning planner orchestration events for the UI."""

    # purpose: deliver real-time planner progress without polling
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    snapshot = cloning_planner.serialize_session(planner)
    branch_filter = str(branch) if branch else None
    since_cursor = since
    seen_since = since_cursor is None
    replay_window = cloning_planner.compose_replay_window(
        planner,
        branch_id=branch_filter,
        stage_filter=stage,
        guardrail_gate=gate,
    )
    comparison_branch = str(compare_branch) if compare_branch else None
    comparison_window = (
        cloning_planner.compose_replay_window(
            planner,
            branch_id=comparison_branch,
            stage_filter=stage,
            guardrail_gate=gate,
        )
        if comparison_branch
        else []
    )
    branch_comparison = (
        cloning_planner.compose_branch_comparison(
            planner,
            branch_id=branch_filter,
            reference_branch_id=comparison_branch,
            stage_filter=stage,
            guardrail_gate=gate,
        )
        if comparison_branch or comparison_window
        else None
    )

    async def event_iterator():
        nonlocal seen_since, replay_window, comparison_window, branch_comparison
        initial_event = {
            "id": snapshot.get("timeline_cursor") or str(uuid4()),
            "type": "snapshot",
            "session_id": str(planner.id),
            "status": snapshot["status"],
            "current_step": snapshot.get("current_step"),
            "guardrail_state": snapshot.get("guardrail_state"),
            "guardrail_gate": snapshot.get("guardrail_gate"),
            "guardrail_transition": {
                "previous": snapshot.get("guardrail_gate"),
                "current": snapshot.get("guardrail_gate"),
            },
            "payload": {
                "snapshot": True,
                "toolkit_recommendations": snapshot.get("toolkit_recommendations"),
                "recovery_context": snapshot.get("recovery_context")
                or snapshot.get("guardrail_state", {}).get("recovery"),
            },
            "branch": {
                "active": str(snapshot.get("active_branch_id")) if snapshot.get("active_branch_id") else None,
                "state": snapshot.get("branch_state"),
            },
            "checkpoint": {
                "key": "snapshot",
                "payload": {
                    "status": snapshot["status"],
                    "branch_id": str(snapshot.get("active_branch_id")) if snapshot.get("active_branch_id") else None,
                },
            },
            "timeline_cursor": snapshot.get("timeline_cursor"),
            "resume_token": {
                "session_id": str(planner.id),
                "checkpoint": "snapshot",
                "branch_id": branch_filter,
                "timeline_cursor": snapshot.get("timeline_cursor"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "branch_lineage_delta": {
                "branch_id": branch_filter,
                "stage": None,
                "history_length": len(replay_window),
            },
            "mitigation_hints": snapshot.get("guardrail_state", {}).get("mitigation_hints", []),
            "recovery_context": snapshot.get("recovery_context")
            or snapshot.get("guardrail_state", {}).get("recovery"),
            "recovery_bundle": snapshot.get("recovery_bundle"),
            "drill_summaries": snapshot.get("drill_summaries", []),
            "replay_window": replay_window,
            "comparison_window": comparison_window,
            "branch_comparison": branch_comparison,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not branch_filter or initial_event["branch"].get("active") == branch_filter:
            yield f"data: {json.dumps(initial_event)}\n\n"
        if not seen_since and initial_event.get("timeline_cursor") == since_cursor:
            seen_since = True
        async for message in pubsub.iter_planner_events(str(planner.id)):
            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                continue
            if branch_filter and (event.get("branch") or {}).get("active") != branch_filter:
                continue
            event_stage = (event.get("payload") or {}).get("stage") or (event.get("checkpoint") or {}).get("key")
            if stage and event_stage != stage:
                continue
            if gate:
                current_gate = ((event.get("guardrail_gate") or {}).get("state")) or (
                    (event.get("guardrail_transition") or {}).get("current") or {}
                ).get("state")
                if current_gate != gate:
                    continue
            if not seen_since:
                if event.get("timeline_cursor") == since_cursor or event.get("id") == since_cursor:
                    seen_since = True
                else:
                    continue
            if comparison_branch:
                lineage = event.get("branch_lineage_delta") or {}
                refreshed = (
                    db.query(models.CloningPlannerSession)
                    .filter(models.CloningPlannerSession.id == planner.id)
                    .first()
                )
                if refreshed:
                    planner_obj = refreshed
                    replay_window = cloning_planner.compose_replay_window(
                        planner_obj,
                        branch_id=branch_filter,
                        stage_filter=stage,
                        guardrail_gate=gate,
                    )
                    comparison_window = cloning_planner.compose_replay_window(
                        planner_obj,
                        branch_id=comparison_branch,
                        stage_filter=stage,
                        guardrail_gate=gate,
                    )
                    branch_comparison = cloning_planner.compose_branch_comparison(
                        planner_obj,
                        branch_id=branch_filter,
                        reference_branch_id=comparison_branch,
                        stage_filter=stage,
                        guardrail_gate=gate,
                    )
                    planner = planner_obj
                    event["replay_window"] = replay_window
                    event["comparison_window"] = comparison_window
                    event["branch_comparison"] = branch_comparison
                else:
                    event["branch_comparison"] = {
                        "reference_branch_id": comparison_branch,
                        "reference_history_length": len(comparison_window),
                        "history_delta": (lineage.get("history_length") or 0) - len(comparison_window),
                        "ahead_checkpoints": [],
                        "missing_checkpoints": [],
                        "divergent_stages": [],
                    }
            yield f"data: {json.dumps(event)}\n\n"
            if await request.is_disconnected():
                break

    return StreamingResponse(event_iterator(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/resume", response_model=schemas.CloningPlannerSessionOut)
def resume_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerResumeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Resume a cloning planner session from the last checkpoint."""

    # purpose: restart Celery orchestration with optional override payloads
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    overrides = payload.overrides or {}
    resume_step = (payload.step or planner.current_step or "primers").lower()
    product_size_range = overrides.get("product_size_range")
    size_range: tuple[int, int] | None = None
    if product_size_range and len(product_size_range) == 2:
        size_range = (int(product_size_range[0]), int(product_size_range[1]))
    task_id = cloning_planner.enqueue_pipeline(
        planner.id,
        product_size_range=size_range,
        target_tm=overrides.get("target_tm"),
        enzymes=overrides.get("enzymes"),
        chromatograms=overrides.get("chromatograms"),
        resume_from=resume_step,
        preset_id=overrides.get("preset_id"),
    )
    db.refresh(planner)
    serialised = cloning_planner.serialize_session(planner)
    if task_id and not serialised.get("celery_task_id"):
        serialised["celery_task_id"] = task_id
    return schemas.CloningPlannerSessionOut(**serialised)


@router.post("/sessions/{session_id}/cancel", response_model=schemas.CloningPlannerSessionOut)
def cancel_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerCancelRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Cancel a cloning planner session and revoke outstanding tasks."""

    # purpose: surface guardrail-aware cancellation checkpoints for operators
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    if planner.celery_task_id:
        celery_app.control.revoke(planner.celery_task_id, terminate=True)
    now = datetime.now(timezone.utc)
    timings = dict(planner.stage_timings or {})
    current_step = planner.current_step or "primers"
    entry = dict(timings.get(current_step) or {})
    entry.update(
        {
            "status": "cancelled",
            "completed_at": now.isoformat(),
            "error": payload.reason,
        }
    )
    timings[current_step] = entry
    planner.stage_timings = timings
    planner.status = "cancelled"
    planner.last_error = payload.reason
    planner.updated_at = now
    planner.celery_task_id = None
    db.add(planner)
    db.commit()
    db.refresh(planner)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(planner))


@router.post("/sessions/{session_id}/steps/{step}", response_model=schemas.CloningPlannerSessionOut)
def record_cloning_planner_stage(
    session_id: UUID,
    step: str,
    payload: schemas.CloningPlannerStageRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Persist stage outputs for a cloning planner session."""

    # purpose: update planner state as operators or background tasks complete stages
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    config = payload.payload or {}
    try:
        normalised_step = step.lower()
        if normalised_step == "primers":
            product_size_range = config.get("product_size_range")
            if product_size_range and len(product_size_range) == 2:
                size_range = (int(product_size_range[0]), int(product_size_range[1]))
            else:
                size_range = None
            updated = cloning_planner.run_primer_design(
                db,
                planner=planner,
                product_size_range=size_range,
                target_tm=config.get("target_tm"),
                preset_id=config.get("preset_id"),
            )
        elif normalised_step == "restriction":
            updated = cloning_planner.run_restriction_analysis(
                db,
                planner=planner,
                enzymes=config.get("enzymes"),
                preset_id=config.get("preset_id"),
            )
        elif normalised_step == "assembly":
            updated = cloning_planner.run_assembly_planning(
                db,
                planner=planner,
                strategy=config.get("strategy"),
                preset_id=config.get("preset_id"),
            )
        elif normalised_step == "qc":
            updated = cloning_planner.run_qc_checks(
                db,
                planner=planner,
                chromatograms=config.get("chromatograms"),
            )
        else:
            updated = cloning_planner.record_stage_progress(
                db,
                planner=planner,
                step=step,
                payload=config,
                next_step=payload.next_step,
                status=payload.status,
                guardrail_state=payload.guardrail_state,
                task_id=payload.task_id,
                error=payload.error,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(updated)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(updated))


@router.post("/sessions/{session_id}/finalize", response_model=schemas.CloningPlannerSessionOut)
def finalize_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerFinalizeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Finalize a cloning planner session after guardrail checks pass."""

    # purpose: conclude planner workflows and record guardrail summary for exports
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    finalized = cloning_planner.finalize_session(
        db,
        planner=planner,
        guardrail_state=payload.guardrail_state,
    )
    db.commit()
    db.refresh(finalized)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(finalized))
