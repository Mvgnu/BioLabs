from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import re
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, Iterable, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from pydantic import ValidationError

from .. import models, schemas, simulation
from .. import pubsub
from ..eventlog import record_execution_event
from ..narratives import render_execution_narrative, render_preview_narrative
from ..services import approval_ladders
from ..auth import get_current_user
from ..database import get_db
from ..recommendations.timeline import load_governance_decision_timeline
from ..storage import (
    generate_signed_download_url,
    load_binary_payload,
    validate_checksum,
)
from ..workers.packaging import (
    enqueue_narrative_export_packaging,
    get_packaging_queue_snapshot,
)

router = APIRouter(prefix="/api/experiment-console", tags=["experiment-console"])
preview_router = APIRouter(prefix="/api/experiments", tags=["experiment-preview"])


def _build_artifact_download_path(execution_id: UUID, export_id: UUID) -> str:
    """Construct the relative API path for retrieving packaged exports."""

    # purpose: centralize artifact download URL construction
    # inputs: execution and export identifiers
    # outputs: API path string for download endpoint consumption
    # status: pilot
    return (
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/artifact"
    )


def _coerce_uuid_or_none(value: Any) -> UUID | None:
    """Attempt to coerce arbitrary payload values into UUIDs."""

    # purpose: safely parse override identifiers stored as JSON strings
    # inputs: untyped value from scenario payloads or overrides
    # outputs: UUID when parsing succeeds or None otherwise
    # status: pilot
    if value in {None, "", 0}:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive guard
        return None


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    """Return timezone-aware datetime for ISO strings."""

    # purpose: safely parse ISO timestamps received from async streams
    # inputs: raw ISO 8601 string or None
    # outputs: timezone-aware datetime instance or None when parsing fails
    # status: pilot
    if not raw:
        return None
    normalised = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _calculate_remaining_seconds(
    expires_at: datetime | None, *, now: datetime | None = None
) -> int | None:
    """Compute integer second delta for cooldown expirations."""

    # purpose: translate cooldown expiry datetimes into UI-friendly countdowns
    # inputs: target expiration datetime and optional reference time
    # outputs: non-negative integer seconds or None when cooldown absent
    # status: pilot
    if expires_at is None:
        return None
    reference = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    remaining = int((expires_at - reference).total_seconds())
    return max(remaining, 0)


def _build_export_payload(
    db: Session, export: models.ExecutionNarrativeExport
) -> schemas.ExecutionNarrativeExport:
    """Serialise an export with guardrail forecasts attached."""

    # purpose: centralise export serialisation with guardrail annotation
    # inputs: database session and execution export ORM instance
    # outputs: ExecutionNarrativeExport schema enriched with guardrail_simulation
    # status: pilot
    approval_ladders.attach_guardrail_forecast(db, export)
    approval_ladders.attach_guardrail_history(db, export)
    return schemas.ExecutionNarrativeExport.model_validate(export)


def _build_escalation_prompt(tier: str | None, level: int | None) -> str | None:
    """Generate concise escalation copy for lock displays."""

    # purpose: craft operator-facing escalation context summaries
    # inputs: tier label and numeric escalation level
    # outputs: formatted escalation phrase or None when not applicable
    # status: pilot
    if not tier and level is None:
        return None
    fragments: list[str] = []
    if tier:
        fragments.append(tier.replace("_", " ").title())
    if level is not None:
        fragments.append(f"Level {level}")
    joined = " · ".join(fragments) if fragments else "Escalation"
    return f"{joined} lock engaged"


def _serialize_override_lock_snapshot(
    record: models.GovernanceOverrideAction,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return structured lock + cooldown state for override actions."""

    # purpose: expose current reversal lock holder and cooldown telemetry
    # inputs: override action ORM record and optional reference time
    # outputs: dictionary snapshot consumed by SSE stream subscribers
    # status: pilot
    reference_time = now or datetime.now(timezone.utc)
    actor = record.reversal_lock_actor
    lock_payload: dict[str, Any] | None = None
    if record.reversal_lock_token:
        lock_payload = {
            "token": record.reversal_lock_token,
            "tier": record.reversal_lock_tier,
            "tier_key": record.reversal_lock_tier_key,
            "tier_level": record.reversal_lock_tier_level,
            "scope": record.reversal_lock_scope,
            "acquired_at": record.reversal_lock_acquired_at.isoformat()
            if record.reversal_lock_acquired_at
            else None,
            "actor": None,
            "escalation_prompt": _build_escalation_prompt(
                record.reversal_lock_tier, record.reversal_lock_tier_level
            ),
        }
        if actor is not None:
            lock_payload["actor"] = {
                "id": str(actor.id),
                "name": actor.full_name,
                "email": actor.email,
            }
    cooldown_payload: dict[str, Any] | None = None
    expires_at = record.cooldown_expires_at
    if expires_at or record.cooldown_window_minutes is not None:
        cooldown_payload = {
            "expires_at": expires_at.isoformat() if expires_at else None,
            "window_minutes": record.cooldown_window_minutes,
            "remaining_seconds": _calculate_remaining_seconds(
                expires_at, now=reference_time
            ),
        }
    snapshot = {
        "override_id": str(record.id),
        "recommendation_id": record.recommendation_id,
        "execution_id": str(record.execution_id)
        if record.execution_id is not None
        else None,
        "execution_hash": record.execution_hash,
        "lock": lock_payload,
        "cooldown": cooldown_payload,
    }
    return snapshot


def _apply_lock_event_state(
    state: dict[str, Any],
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mutate stored lock snapshot using the latest event payload."""

    # purpose: reconcile redis pub/sub payloads with cached lock states
    # inputs: existing lock snapshot, raw event payload, optional reference time
    # outputs: updated snapshot dictionary (mutated in place for efficiency)
    # status: pilot
    if "lock" not in state:
        state["lock"] = None
    if "cooldown" not in state or state["cooldown"] is None:
        state["cooldown"] = {
            "expires_at": None,
            "window_minutes": None,
            "remaining_seconds": None,
        }
    lock_event = payload.get("lock_event") or payload
    event_type = lock_event.get("event_type")
    if event_type == "released":
        state["lock"] = None
    else:
        state["lock"] = {
            "token": lock_event.get("lock_token"),
            "tier": lock_event.get("tier"),
            "tier_key": lock_event.get("tier_key"),
            "tier_level": lock_event.get("tier_level"),
            "scope": lock_event.get("scope"),
            "actor": lock_event.get("actor"),
            "reason": lock_event.get("reason"),
            "created_at": lock_event.get("created_at"),
            "escalation_prompt": _build_escalation_prompt(
                lock_event.get("tier"), lock_event.get("tier_level")
            ),
        }
    cooldown_section = state.get("cooldown") or {}
    expires_raw = lock_event.get("cooldown_expires_at")
    if expires_raw is not None:
        cooldown_section = dict(cooldown_section)
        cooldown_section["expires_at"] = expires_raw
        parsed = _parse_iso_datetime(expires_raw)
        cooldown_section["remaining_seconds"] = _calculate_remaining_seconds(
            parsed, now=now
        )
        state["cooldown"] = cooldown_section
    window_raw = lock_event.get("cooldown_window_minutes")
    if window_raw is not None:
        cooldown_section = dict(state.get("cooldown") or {})
        cooldown_section["window_minutes"] = window_raw
        state["cooldown"] = cooldown_section
    return state


def _render_sse_payload(payload: dict[str, Any]) -> str:
    """Format dictionaries into SSE compliant frames."""

    # purpose: centralize SSE framing with JSON serialization
    # inputs: payload dictionary destined for event-stream clients
    # outputs: SSE data line string with terminating newline block
    # status: pilot
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _normalize_resource_overrides(
    payload: dict[str, Any] | None,
) -> schemas.ExperimentPreviewResourceOverrides | None:
    """Return sanitized resource override configuration."""

    # purpose: translate persisted scenario resource overrides into schema objects
    # inputs: raw JSON dict from ExperimentScenario.resource_overrides
    # outputs: ExperimentPreviewResourceOverrides or None when empty
    # status: pilot
    if not isinstance(payload, dict):
        return None
    cleaned: dict[str, list[str]] = {}
    for key in ("inventory_item_ids", "booking_ids", "equipment_ids"):
        raw_values = payload.get(key)
        if not isinstance(raw_values, (list, tuple)):
            continue
        normalized: list[str] = []
        for entry in raw_values:
            value = _coerce_uuid_or_none(entry)
            if value is not None:
                normalized.append(str(value))
        if normalized:
            cleaned[key] = normalized
    if not cleaned:
        return None
    return schemas.ExperimentPreviewResourceOverrides(**cleaned)


def _normalize_stage_overrides(
    payload: Sequence[dict[str, Any]] | None,
) -> list[schemas.ExperimentPreviewStageOverride]:
    """Return sanitized stage override configuration."""

    # purpose: translate persisted scenario stage overrides into schema objects
    # inputs: list of dict payloads from ExperimentScenario.stage_overrides
    # outputs: list[ExperimentPreviewStageOverride] sorted by index
    # status: pilot
    if not isinstance(payload, (list, tuple)):
        return []
    normalized: list[schemas.ExperimentPreviewStageOverride] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            index_value = int(raw.get("index"))
        except (TypeError, ValueError):
            continue
        normalized.append(
            schemas.ExperimentPreviewStageOverride(
                index=index_value,
                sla_hours=
                raw.get("sla_hours") if isinstance(raw.get("sla_hours"), int) else None,
                assignee_id=_coerce_uuid_or_none(raw.get("assignee_id")),
                delegate_id=_coerce_uuid_or_none(raw.get("delegate_id")),
            )
        )
    normalized.sort(key=lambda item: item.index)
    return normalized


def _prepare_resource_override_payload(
    overrides: schemas.ExperimentPreviewResourceOverrides | None,
) -> dict[str, list[str]]:
    """Convert resource override schema into JSON-serialisable payload."""

    # purpose: store scientist-authored resource overrides without UUID objects
    # inputs: ExperimentPreviewResourceOverrides from API payloads
    # outputs: dict of identifier lists suitable for JSON persistence
    # status: pilot
    if overrides is None:
        return {}
    payload = overrides.model_dump(exclude_none=True)
    sanitized: dict[str, list[str]] = {}
    for key, values in payload.items():
        if not isinstance(values, list):
            continue
        sanitized[key] = []
        for entry in values:
            try:
                sanitized[key].append(str(UUID(str(entry))))
            except (TypeError, ValueError):
                continue
        if not sanitized[key]:
            sanitized.pop(key, None)
    return sanitized


def _prepare_stage_override_payload(
    overrides: Sequence[schemas.ExperimentPreviewStageOverride] | None,
) -> list[dict[str, Any]]:
    """Convert stage override schemas into JSON payload."""

    # purpose: persist stage overrides with primitive types for JSON storage
    # inputs: list of ExperimentPreviewStageOverride
    # outputs: list of dict payloads with serialisable primitives
    # status: pilot
    if not overrides:
        return []
    payload: list[dict[str, Any]] = []
    for override in overrides:
        override_dict = override.model_dump(exclude_none=True)
        override_payload: dict[str, Any] = {"index": int(override_dict.get("index", 0))}
        if "sla_hours" in override_dict:
            override_payload["sla_hours"] = override_dict["sla_hours"]
        for key in ("assignee_id", "delegate_id"):
            value = override_dict.get(key)
            if value:
                try:
                    override_payload[key] = str(UUID(str(value)))
                except (TypeError, ValueError):
                    continue
        payload.append(override_payload)
    return payload


def _normalize_shared_team_ids(values: Iterable[Any] | None) -> list[str]:
    """Return sanitized list of team identifiers for sharing metadata."""

    # purpose: harmonize shared team payloads for persistence
    # inputs: iterable of arbitrary values supplied by clients
    # outputs: list of UUID strings safe for storage
    # status: pilot
    normalized: list[str] = []
    if not values:
        return normalized
    for value in values:
        team_id = _coerce_uuid_or_none(value)
        if team_id is not None:
            normalized.append(str(team_id))
    return normalized


def _get_user_team_ids(db: Session, user: models.User) -> set[UUID]:
    """Return team memberships for the authenticated user."""

    # purpose: support RBAC decisions across scenario workspace endpoints
    # inputs: database session and authenticated user record
    # outputs: set of team UUIDs where the user is a member
    # status: pilot
    if user.is_admin:
        return set()
    rows = (
        db.query(models.TeamMember.team_id)
        .filter(models.TeamMember.user_id == user.id)
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _ensure_execution_access(
    db: Session,
    execution: models.ProtocolExecution,
    user: models.User,
    team_ids: set[UUID] | None = None,
) -> models.ProtocolTemplate:
    """Raise when a user lacks permission to interact with the execution."""

    # purpose: centralise RBAC enforcement for scenario workspace endpoints
    # inputs: execution record, authenticated user, optional cached team ids
    # outputs: associated protocol template when authorised
    # status: pilot
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if user.is_admin or execution.run_by == user.id:
        template = execution.template or db.get(models.ProtocolTemplate, execution.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Protocol template not found")
        return template
    template = execution.template or db.get(models.ProtocolTemplate, execution.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Protocol template not found")
    membership_ids = team_ids if team_ids is not None else _get_user_team_ids(db, user)
    if template.team_id and membership_ids and template.team_id in membership_ids:
        return template
    raise HTTPException(status_code=403, detail="Not authorized for execution workspace")


def _compose_preview_analytics_payload(
    insights: Sequence[schemas.ExperimentPreviewStageInsight],
    generated_at: datetime,
    snapshot: models.ExecutionNarrativeWorkflowTemplateSnapshot,
    baseline_snapshot: models.ExecutionNarrativeWorkflowTemplateSnapshot | None,
    stage_overrides: dict[int, dict[str, Any]],
    resource_warnings: Sequence[str],
) -> dict[str, Any]:
    """Summarize preview telemetry for downstream governance analytics."""

    # purpose: condense preview insight metrics into analytics event payloads
    # inputs: stage insight collection, generated timestamp, template snapshot context
    # outputs: dictionary payload persisted via execution event log utilities
    # status: pilot
    blocked_stage_indexes: list[int] = []
    stage_predictions: list[dict[str, Any]] = []
    new_blocker_total = 0
    resolved_blocker_total = 0
    delta_projection_minutes: list[int] = []

    for stage in insights:
        projected_due = (
            stage.projected_due_at.isoformat()
            if getattr(stage, "projected_due_at", None)
            else None
        )
        baseline_due = (
            stage.baseline_projected_due_at.isoformat()
            if getattr(stage, "baseline_projected_due_at", None)
            else None
        )
        if stage.status == "blocked":
            blocked_stage_indexes.append(stage.index)
        new_blocker_total += len(stage.delta_new_blockers)
        resolved_blocker_total += len(stage.delta_resolved_blockers)
        if stage.delta_projected_due_minutes is not None:
            delta_projection_minutes.append(stage.delta_projected_due_minutes)
        stage_predictions.append(
            {
                "index": stage.index,
                "status": stage.status,
                "projected_due_at": projected_due,
                "baseline_projected_due_at": baseline_due,
                "mapped_step_indexes": list(stage.mapped_step_indexes),
                "delta_status": stage.delta_status,
                "delta_projected_due_minutes": stage.delta_projected_due_minutes,
            }
        )

    blocked_stage_count = len(blocked_stage_indexes)
    stage_count = len(insights)

    return {
        "generated_at": generated_at.isoformat(),
        "snapshot_id": str(snapshot.id),
        "baseline_snapshot_id": str(baseline_snapshot.id)
        if baseline_snapshot
        else None,
        "stage_count": stage_count,
        "blocked_stage_count": blocked_stage_count,
        "blocked_stage_indexes": blocked_stage_indexes,
        "override_count": len(stage_overrides),
        "new_blocker_count": new_blocker_total,
        "resolved_blocker_count": resolved_blocker_total,
        "resource_warning_count": len(resource_warnings),
        "delta_projection_minutes": delta_projection_minutes,
        "stage_predictions": stage_predictions,
    }


def _resolve_assigned_template_ids(
    db: Session,
    template: models.ProtocolTemplate,
) -> set[UUID]:
    """Determine governance workflow template ids assigned to the protocol context."""

    # purpose: constrain scenario workspace snapshots to assigned governance templates
    # inputs: protocol template
    # outputs: set of workflow template UUIDs bound to the execution context
    # status: pilot
    if template is None:
        return set()
    filters = [
        models.ExecutionNarrativeWorkflowTemplateAssignment.protocol_template_id
        == template.id
    ]
    if template.team_id:
        filters.append(
            models.ExecutionNarrativeWorkflowTemplateAssignment.team_id == template.team_id
        )
    query = db.query(models.ExecutionNarrativeWorkflowTemplateAssignment)
    if len(filters) == 1:
        query = query.filter(filters[0])
    else:
        query = query.filter(or_(*filters))
    assignments = query.all()
    return {assignment.template_id for assignment in assignments if assignment.template_id}


def _serialize_scenario(
    scenario: models.ExperimentScenario,
) -> schemas.ExperimentScenario:
    """Convert database scenario row into API schema."""

    # purpose: provide consistent API representation for workspace responses
    # inputs: ExperimentScenario ORM instance
    # outputs: ExperimentScenario schema with normalized overrides
    # status: pilot
    resource_overrides = _normalize_resource_overrides(scenario.resource_overrides)
    stage_overrides = _normalize_stage_overrides(scenario.stage_overrides)
    shared_team_ids: list[UUID] = []
    raw_shared = scenario.shared_team_ids or []
    for entry in raw_shared:
        try:
            shared_team_ids.append(UUID(str(entry)))
        except (TypeError, ValueError):
            continue

    expires_at = scenario.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return schemas.ExperimentScenario(
        id=scenario.id,
        execution_id=scenario.execution_id,
        owner_id=scenario.owner_id,
        team_id=scenario.team_id,
        workflow_template_snapshot_id=scenario.workflow_template_snapshot_id,
        name=scenario.name,
        description=scenario.description,
        resource_overrides=resource_overrides,
        stage_overrides=stage_overrides,
        cloned_from_id=scenario.cloned_from_id,
        folder_id=scenario.folder_id,
        is_shared=bool(scenario.is_shared),
        shared_team_ids=shared_team_ids,
        expires_at=expires_at,
        timeline_event_id=scenario.timeline_event_id,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


def _serialize_folder(
    folder: models.ExperimentScenarioFolder,
) -> schemas.ExperimentScenarioFolder:
    """Convert folder ORM row into API schema."""

    # purpose: surface folder metadata for workspace navigation
    # inputs: ExperimentScenarioFolder ORM row
    # outputs: ExperimentScenarioFolder schema
    # status: pilot
    return schemas.ExperimentScenarioFolder(
        id=folder.id,
        execution_id=folder.execution_id,
        name=folder.name,
        description=folder.description,
        owner_id=folder.owner_id,
        team_id=folder.team_id,
        visibility=folder.visibility,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _folder_accessible(
    folder: models.ExperimentScenarioFolder,
    user: models.User,
    team_ids: set[UUID],
) -> bool:
    """Return True when the folder is visible to the requester."""

    # purpose: reuse RBAC semantics for folder navigation decisions
    # inputs: folder ORM row, requesting user, cached team identifiers
    # outputs: boolean access decision
    # status: pilot
    if user.is_admin or folder.owner_id == user.id:
        return True
    if folder.visibility == "execution":
        return True
    if folder.visibility == "team" and folder.team_id and folder.team_id in team_ids:
        return True
    if folder.team_id and folder.team_id in team_ids:
        return True
    return False


def _scenario_accessible(
    scenario: models.ExperimentScenario,
    user: models.User,
    team_ids: set[UUID],
) -> bool:
    """Return True when the scenario is visible to the requester."""

    # purpose: centralise scenario visibility logic with sharing metadata
    # inputs: scenario ORM row, authenticated user, cached team ids
    # outputs: boolean access decision used by workspace listing
    # status: pilot
    if user.is_admin or scenario.owner_id == user.id:
        return True
    if scenario.team_id and scenario.team_id in team_ids:
        return True
    if scenario.folder and _folder_accessible(scenario.folder, user, team_ids):
        return True
    if scenario.is_shared:
        shared_memberships = {
            value
            for entry in (scenario.shared_team_ids or [])
            if (value := _coerce_uuid_or_none(entry)) is not None
        }
        if shared_memberships & team_ids:
            return True
    return False


def _validate_folder_assignment(
    db: Session,
    execution: models.ProtocolExecution,
    folder_id: UUID | None,
    user: models.User,
    team_ids: set[UUID],
) -> models.ExperimentScenarioFolder | None:
    """Ensure a requested folder belongs to the execution and is accessible."""

    # purpose: centralise folder RBAC validation for create/update flows
    # inputs: database session, execution, requested folder identifier, user context
    # outputs: ExperimentScenarioFolder or None when not provided
    # status: pilot
    if folder_id is None:
        return None
    folder = db.get(models.ExperimentScenarioFolder, folder_id)
    if not folder or folder.execution_id != execution.id:
        raise HTTPException(status_code=404, detail="Scenario folder not found")
    if user.is_admin or folder.owner_id == user.id:
        return folder
    if not _folder_accessible(folder, user, team_ids):
        raise HTTPException(status_code=403, detail="Not authorised to use this folder")
    return folder


def _validate_timeline_event_binding(
    db: Session,
    execution: models.ProtocolExecution,
    event_id: UUID | None,
) -> models.ExecutionEvent | None:
    """Ensure the referenced timeline event belongs to the execution."""

    # purpose: guarantee timeline anchors reflect execution history
    # inputs: database session, execution context, optional event id
    # outputs: ExecutionEvent row or None
    # status: pilot
    if event_id is None:
        return None
    event = db.get(models.ExecutionEvent, event_id)
    if not event or event.execution_id != execution.id:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    return event

def _parse_uuid_list(values: Iterable[Any]) -> list[UUID]:
    """
    Convert provided iterable to UUID list while skipping invalid entries.
    """

    # purpose: sanitize incoming identifier collections for downstream queries
    # inputs: iterable of raw identifiers from execution params or payloads
    # outputs: list[UUID] containing only valid identifiers
    # status: production
    parsed: list[UUID] = []
    for value in values:
        try:
            parsed.append(UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return parsed


def _coerce_datetime(value: Any) -> datetime | None:
    """Normalize arbitrary datetime payloads into aware datetime objects."""

    # purpose: ensure timeline metadata remains parseable by Pydantic schemas
    # inputs: value possibly str/datetime/None from execution.result
    # outputs: datetime object or None when parsing fails
    # status: production
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _iso_or_none(value: datetime | None) -> str | None:
    """Serialize datetime values for storage inside JSON columns."""

    # purpose: store timeline metadata inside ProtocolExecution.result
    # inputs: datetime or None from update payload
    # outputs: ISO formatted string or None
    # status: production
    if value is None:
        return None
    return value.isoformat()


def _extract_steps(content: str) -> list[str]:
    """Return ordered execution steps derived from a protocol body."""

    # purpose: infer actionable instructions for the console surface
    # inputs: protocol template content string
    # outputs: ordered list of non-empty instruction strings
    # status: production
    steps: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        steps.append(line)
    return steps


def _build_step_states(
    execution: models.ProtocolExecution,
    instructions: list[str],
    gate_context: dict[str, Any],
) -> list[schemas.ExperimentStepStatus]:
    """Combine instructions with persisted execution progress."""

    # purpose: align persisted step status metadata with derived instructions
    # inputs: execution record, list of instruction strings, gating context for readiness checks
    # outputs: ExperimentStepStatus objects representing current progress and gating metadata
    # status: pilot
    result_payload = execution.result or {}
    stored_steps = result_payload.get("steps", {}) if isinstance(result_payload, dict) else {}
    step_statuses: list[schemas.ExperimentStepStatus] = []

    for index, instruction in enumerate(instructions):
        stored = stored_steps.get(str(index), {}) if isinstance(stored_steps, dict) else {}
        status = stored.get("status", "pending")
        started_at = _coerce_datetime(stored.get("started_at"))
        completed_at = _coerce_datetime(stored.get("completed_at"))

        if status in {"completed", "skipped"}:
            blocked_reason: str | None = None
            required_actions: list[str] = []
            auto_triggers: list[str] = []
        else:
            blocked_reason, required_actions, auto_triggers = _evaluate_step_gate(
                index, gate_context, status
            )

        step_statuses.append(
            schemas.ExperimentStepStatus(
                index=index,
                instruction=instruction,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                blocked_reason=blocked_reason,
                required_actions=required_actions,
                auto_triggers=auto_triggers,
            )
        )
    return step_statuses


def _prepare_step_gate_context(
    db: Session,
    execution: models.ProtocolExecution,
    inventory_items: Sequence[models.InventoryItem],
    bookings: Sequence[models.Booking],
) -> dict[str, Any]:
    """Aggregate resource metadata for gating evaluations."""

    # purpose: centralize readiness signals for orchestration engine
    # inputs: database session, execution record, hydrated inventory & booking rows
    # outputs: dictionary containing maps/sets leveraged during gating checks
    # status: pilot
    params = execution.params or {}
    step_requirements_raw = params.get("step_requirements", {})
    if not isinstance(step_requirements_raw, dict):
        step_requirements_raw = {}

    default_inventory_ids = set(_parse_uuid_list(params.get("inventory_item_ids", [])))
    default_booking_ids = set(_parse_uuid_list(params.get("booking_ids", [])))
    default_equipment_ids = set(_parse_uuid_list(params.get("equipment_ids", [])))

    additional_inventory_ids: set[UUID] = set()
    additional_booking_ids: set[UUID] = set()
    additional_equipment_ids: set[UUID] = set()
    for config in step_requirements_raw.values():
        if not isinstance(config, dict):
            continue
        additional_inventory_ids.update(
            _parse_uuid_list(config.get("required_inventory_ids", []))
        )
        additional_booking_ids.update(
            _parse_uuid_list(config.get("required_booking_ids", []))
        )
        additional_equipment_ids.update(
            _parse_uuid_list(config.get("required_equipment_ids", []))
        )

    inventory_map = {item.id: item for item in inventory_items}
    missing_inventory_ids = (default_inventory_ids | additional_inventory_ids) - set(
        inventory_map
    )
    if missing_inventory_ids:
        fetched_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(list(missing_inventory_ids)))
            .all()
        )
        for item in fetched_items:
            inventory_map[item.id] = item

    booking_map = {booking.id: booking for booking in bookings}
    missing_booking_ids = (default_booking_ids | additional_booking_ids) - set(
        booking_map
    )
    if missing_booking_ids:
        fetched_bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(list(missing_booking_ids)))
            .all()
        )
        for booking in fetched_bookings:
            booking_map[booking.id] = booking

    equipment_ids = default_equipment_ids | additional_equipment_ids
    equipment_rows: list[models.Equipment] = []
    if equipment_ids:
        equipment_rows = (
            db.query(models.Equipment)
            .filter(models.Equipment.id.in_(list(equipment_ids)))
            .all()
        )
    equipment_map = {equipment.id: equipment for equipment in equipment_rows}

    maintenance_map: dict[UUID, list[models.EquipmentMaintenance]] = {}
    if equipment_ids:
        maintenance_rows = (
            db.query(models.EquipmentMaintenance)
            .filter(models.EquipmentMaintenance.equipment_id.in_(list(equipment_ids)))
            .all()
        )
        for task in maintenance_rows:
            maintenance_map.setdefault(task.equipment_id, []).append(task)

    result_payload = execution.result if isinstance(execution.result, dict) else {}
    compliance_payload = (
        result_payload.get("compliance", {}) if isinstance(result_payload, dict) else {}
    )
    granted_approvals = set()
    if isinstance(compliance_payload, dict):
        raw_approvals = compliance_payload.get("approvals", [])
        if isinstance(raw_approvals, (list, tuple, set)):
            granted_approvals = {str(value) for value in raw_approvals}

    global_required_approvals = set()
    raw_required = params.get("required_approvals", [])
    if isinstance(raw_required, (list, tuple, set)):
        global_required_approvals = {str(value) for value in raw_required}

    return {
        "inventory": inventory_map,
        "bookings": booking_map,
        "equipment": equipment_map,
        "maintenance": maintenance_map,
        "step_requirements": step_requirements_raw,
        "default_inventory_ids": list(default_inventory_ids),
        "default_booking_ids": list(default_booking_ids),
        "default_equipment_ids": list(default_equipment_ids),
        "granted_approvals": granted_approvals,
        "global_required_approvals": global_required_approvals,
        "now": datetime.now(timezone.utc),
    }


def _apply_preview_resource_overrides(
    gate_context: dict[str, Any],
    overrides: schemas.ExperimentPreviewResourceOverrides | None,
) -> list[str]:
    """Mutate gate context with simulated resources for preview purposes."""

    # purpose: allow preview simulations to account for hypothetical resources
    # inputs: prepared gate context and optional override payload
    # outputs: list of warnings describing ignored overrides or placeholders
    # status: pilot
    warnings: list[str] = []
    if not overrides:
        return warnings

    now = gate_context.get("now", datetime.now(timezone.utc))
    inventory_map: dict[UUID, Any] = gate_context.setdefault("inventory", {})
    booking_map: dict[UUID, Any] = gate_context.setdefault("bookings", {})
    equipment_map: dict[UUID, Any] = gate_context.setdefault("equipment", {})
    default_inventory_ids: list[UUID] = gate_context.setdefault("default_inventory_ids", [])
    default_booking_ids: list[UUID] = gate_context.setdefault("default_booking_ids", [])
    default_equipment_ids: list[UUID] = gate_context.setdefault("default_equipment_ids", [])

    def _register_inventory(identifier: UUID) -> None:
        if identifier in inventory_map:
            return
        inventory_map[identifier] = SimpleNamespace(
            id=identifier,
            name=f"Simulated Inventory {identifier}",
            status="available",
        )
        if identifier not in default_inventory_ids:
            default_inventory_ids.append(identifier)

    for inventory_id in overrides.inventory_item_ids:
        if isinstance(inventory_id, UUID):
            _register_inventory(inventory_id)
        else:
            warnings.append(f"Invalid inventory override ignored: {inventory_id}")

    def _register_booking(identifier: UUID) -> None:
        if identifier in booking_map:
            return
        booking_map[identifier] = SimpleNamespace(
            id=identifier,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        if identifier not in default_booking_ids:
            default_booking_ids.append(identifier)

    for booking_id in overrides.booking_ids:
        if isinstance(booking_id, UUID):
            _register_booking(booking_id)
        else:
            warnings.append(f"Invalid booking override ignored: {booking_id}")

    def _register_equipment(identifier: UUID) -> None:
        if identifier in equipment_map:
            return
        equipment_map[identifier] = SimpleNamespace(
            id=identifier,
            name=f"Simulated Equipment {identifier}",
            status="available",
        )
        if identifier not in default_equipment_ids:
            default_equipment_ids.append(identifier)

    for equipment_id in overrides.equipment_ids:
        if isinstance(equipment_id, UUID):
            _register_equipment(equipment_id)
        else:
            warnings.append(f"Invalid equipment override ignored: {equipment_id}")

    return warnings


def _evaluate_step_gate(
    step_index: int,
    gate_context: dict[str, Any],
    current_status: str,
) -> tuple[str | None, list[str], list[str]]:
    """Evaluate whether a step is blocked by resource or compliance gates."""

    # purpose: derive orchestrator feedback describing blockers and remediation paths
    # inputs: step index, aggregated gate context, current status string
    # outputs: tuple of blocked reason, required actions, and auto trigger hints
    # status: pilot
    step_requirements = gate_context.get("step_requirements", {}) or {}
    raw_config = step_requirements.get(str(step_index)) or step_requirements.get(step_index)
    step_config = raw_config if isinstance(raw_config, dict) else {}

    blocked_messages: list[str] = []
    required_actions: list[str] = []
    auto_triggers: list[str] = []
    now = gate_context.get("now", datetime.now(timezone.utc))

    def _collect_ids(
        config_key: str, default_ids: list[UUID], fallback_flag: str | None = None
    ) -> list[UUID]:
        if config_key in step_config:
            return _parse_uuid_list(step_config.get(config_key, []))
        if fallback_flag and step_config.get(fallback_flag):
            return default_ids
        return default_ids

    inventory_map: dict[UUID, models.InventoryItem] = gate_context.get("inventory", {})
    booking_map: dict[UUID, models.Booking] = gate_context.get("bookings", {})
    equipment_map: dict[UUID, models.Equipment] = gate_context.get("equipment", {})
    maintenance_map: dict[UUID, list[models.EquipmentMaintenance]] = gate_context.get(
        "maintenance", {}
    )

    required_inventory_ids = _collect_ids(
        "required_inventory_ids", gate_context.get("default_inventory_ids", [])
    )
    for inventory_id in required_inventory_ids:
        item = inventory_map.get(inventory_id)
        if not item:
            blocked_messages.append(
                f"Inventory {inventory_id} is not linked to this execution"
            )
            required_actions.append(f"inventory:link:{inventory_id}")
            continue
        status = (item.status or "").lower()
        if status not in {"available", "reserved"}:
            blocked_messages.append(
                f"Inventory {item.name} unavailable (status: {item.status})"
            )
            required_actions.append(f"inventory:restore:{inventory_id}")
            auto_triggers.append(f"inventory:auto_reserve:{inventory_id}")

    required_booking_ids = _collect_ids(
        "required_booking_ids", gate_context.get("default_booking_ids", [])
    )
    for booking_id in required_booking_ids:
        booking = booking_map.get(booking_id)
        if not booking:
            blocked_messages.append(f"Booking {booking_id} missing for execution")
            required_actions.append(f"booking:create:{booking_id}")
            continue
        start_time = booking.start_time
        end_time = booking.end_time
        if start_time and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time and end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        if end_time is None:
            blocked_messages.append("Booking end time missing for execution")
            required_actions.append(f"booking:adjust:{booking_id}")
            continue
        if not (start_time <= now <= end_time):
            blocked_messages.append(
                "Active booking window not aligned with current time"
            )
            required_actions.append(f"booking:adjust:{booking_id}")

    required_equipment_ids = _collect_ids(
        "required_equipment_ids", gate_context.get("default_equipment_ids", [])
    )
    for equipment_id in required_equipment_ids:
        equipment = equipment_map.get(equipment_id)
        if not equipment:
            blocked_messages.append(f"Equipment {equipment_id} not registered")
            required_actions.append(f"equipment:register:{equipment_id}")
            continue
        overdue = False
        for task in maintenance_map.get(equipment_id, []):
            due_date = task.due_date
            if due_date and due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            if task.completed_at is None and due_date and due_date < now:
                overdue = True
                break
        if overdue:
            blocked_messages.append(
                f"Equipment {equipment.name} has overdue calibration"
            )
            required_actions.append(f"equipment:calibrate:{equipment_id}")
            auto_triggers.append(f"equipment:maintenance_request:{equipment_id}")

    granted = gate_context.get("granted_approvals", set())
    global_required = gate_context.get("global_required_approvals", set())
    step_required = set(step_config.get("required_approvals", []) or [])
    missing_approvals = {str(value) for value in step_required | global_required} - granted
    if missing_approvals and current_status == "pending":
        blocked_messages.append(
            "Pending approvals required: " + ", ".join(sorted(missing_approvals))
        )
        for approval in sorted(missing_approvals):
            required_actions.append(f"compliance:approve:{approval}")
            auto_triggers.append(f"notify:approver:{approval}")

    dedup_required = list(dict.fromkeys(required_actions))
    dedup_triggers = list(dict.fromkeys(auto_triggers))

    blocked_reason = " | ".join(blocked_messages) if blocked_messages else None
    return blocked_reason, dedup_required, dedup_triggers


def _apply_remediation_actions(
    db: Session,
    execution: models.ProtocolExecution,
    step_index: int,
    actions: Sequence[str],
    gate_context: dict[str, Any],
    user: models.User,
    request_context: dict[str, Any] | None = None,
) -> list[schemas.ExperimentRemediationResult]:
    """Execute orchestrator remediation flows for the requested step."""

    # purpose: convert orchestration-required actions into transactional state updates
    # inputs: database session, execution record, target step index, candidate action codes,
    #         aggregated gate context, acting user, optional contextual hints
    # outputs: list of ExperimentRemediationResult summarizing execution outcomes
    # status: pilot
    if not actions:
        return []

    now = datetime.now(timezone.utc)
    context = request_context or {}

    execution_result_raw = execution.result if isinstance(execution.result, dict) else {}
    execution_result = dict(execution_result_raw)
    params = dict(execution.params or {})

    locks_payload = dict(execution_result.get("locks") or {})
    followups_payload = list(execution_result.get("followups") or [])
    remediation_log = list(execution_result.get("remediation_log") or [])

    results: list[schemas.ExperimentRemediationResult] = []
    step_key = str(step_index)
    mutated_execution = False
    mutated_params = False

    def _register_lock(lock_type: str, target: str, state: str) -> None:
        """Ensure the remediation lock ledger reflects the latest resource state."""

        nonlocal mutated_execution
        lock_entries = list(locks_payload.get(step_key, []))
        payload = {
            "type": lock_type,
            "target": target,
            "state": state,
            "execution_id": str(execution.id),
            "step_index": step_index,
            "timestamp": now.isoformat(),
        }
        for entry in lock_entries:
            if entry.get("type") == lock_type and entry.get("target") == target:
                entry.update(payload)
                break
        else:
            lock_entries.append(payload)
        locks_payload[step_key] = lock_entries
        mutated_execution = True

    def _register_followup(
        followup_type: str,
        target: str,
        message: str,
        status: str = "scheduled",
        eta: datetime | None = None,
    ) -> None:
        """Track scheduled remediation follow-ups for transparency."""

        nonlocal mutated_execution
        payload = {
            "type": followup_type,
            "target": target,
            "status": status,
            "message": message,
            "step_index": step_index,
            "created_at": now.isoformat(),
        }
        if eta:
            payload["eta"] = eta.isoformat()
        for entry in followups_payload:
            if (
                entry.get("type") == followup_type
                and entry.get("target") == target
                and entry.get("step_index") == step_index
            ):
                entry.update(payload)
                break
        else:
            followups_payload.append(payload)
        mutated_execution = True

    def _result(action: str, status: str, message: str | None = None) -> None:
        results.append(
            schemas.ExperimentRemediationResult(action=action, status=status, message=message)
        )

    for action in actions:
        normalized = (action or "").strip()
        if not normalized:
            continue
        parts = normalized.split(":")
        domain = parts[0] if parts else ""
        verb = parts[1] if len(parts) > 1 else ""
        identifier = parts[2] if len(parts) > 2 else ""

        if domain == "inventory" and verb in {"restore", "auto_reserve"}:
            try:
                inventory_uuid = UUID(str(identifier))
            except ValueError:
                _result(normalized, "failed", "Invalid inventory identifier")
                continue
            item = (
                db.query(models.InventoryItem)
                .filter(models.InventoryItem.id == inventory_uuid)
                .first()
            )
            if not item:
                _result(normalized, "failed", "Inventory item not found")
                continue
            custom_data = dict(item.custom_data or {})
            reservation_entry = {
                "execution_id": str(execution.id),
                "step_index": step_index,
                "user_id": str(user.id),
                "timestamp": now.isoformat(),
            }
            history = list(custom_data.get("reservation_history") or [])
            history.append(reservation_entry)
            custom_data["reservation_history"] = history[-20:]
            if verb == "auto_reserve":
                item.status = "reserved"
                custom_data["reserved_for_execution"] = str(execution.id)
                _register_lock("inventory", str(inventory_uuid), "locked")
                message = f"Inventory {item.name} reserved for execution"
            else:
                item.status = "available"
                if custom_data.get("reserved_for_execution") == str(execution.id):
                    custom_data.pop("reserved_for_execution", None)
                _register_lock("inventory", str(inventory_uuid), "released")
                message = f"Inventory {item.name} restored to available"
            item.custom_data = custom_data
            mutated_execution = True
            _result(normalized, "executed", message)
            continue

        if domain == "booking" and verb in {"adjust", "create"}:
            bookings_context = context.get("booking") or {}
            booking_context = {}
            if isinstance(bookings_context, dict):
                booking_context = bookings_context.get(identifier) or {}
            start_override = _coerce_datetime(booking_context.get("start_time"))
            end_override = _coerce_datetime(booking_context.get("end_time"))
            duration_minutes = booking_context.get("duration_minutes")
            if duration_minutes is not None:
                try:
                    duration_minutes = max(15, int(duration_minutes))
                except (TypeError, ValueError):
                    duration_minutes = None
            start_time = start_override or now
            computed_end = end_override
            if not computed_end:
                minutes = duration_minutes or 60
                computed_end = start_time + timedelta(minutes=minutes)

            if verb == "adjust":
                try:
                    booking_uuid = UUID(str(identifier))
                except ValueError:
                    _result(normalized, "failed", "Invalid booking identifier")
                    continue
                booking = (
                    db.query(models.Booking)
                    .filter(models.Booking.id == booking_uuid)
                    .first()
                )
                if not booking:
                    _result(normalized, "failed", "Booking not found")
                    continue
                booking.start_time = start_time
                booking.end_time = computed_end
                note_suffix = f"Auto-adjusted for execution {execution.id}"
                booking.notes = (
                    f"{booking.notes}\n{note_suffix}" if booking.notes else note_suffix
                )
                _register_lock("booking", str(booking.id), "locked")
                _result(
                    normalized,
                    "executed",
                    "Booking window aligned with current step",
                )
                continue

            resource_hint = booking_context.get("resource_id")
            if not resource_hint:
                _register_followup(
                    "booking",
                    identifier or "unspecified",
                    "Insufficient context to auto-create booking",
                )
                _result(
                    normalized,
                    "scheduled",
                    "Follow-up scheduled for booking creation",
                )
                continue
            try:
                resource_uuid = UUID(str(resource_hint))
            except ValueError:
                _result(normalized, "failed", "Invalid resource identifier for booking")
                continue
            new_booking = models.Booking(
                resource_id=resource_uuid,
                user_id=user.id,
                start_time=start_time,
                end_time=computed_end,
                notes=booking_context.get(
                    "notes", f"Auto-reservation for execution {execution.id}"
                ),
            )
            db.add(new_booking)
            db.flush()
            existing_booking_ids = _parse_uuid_list(params.get("booking_ids", []))
            if new_booking.id not in existing_booking_ids:
                existing_booking_ids.append(new_booking.id)
                params["booking_ids"] = [str(value) for value in existing_booking_ids]
                mutated_params = True
            _register_lock("booking", str(new_booking.id), "locked")
            _result(
                normalized,
                "executed",
                "Booking created and attached to execution",
            )
            continue

        if domain == "equipment" and verb in {"calibrate", "maintenance_request"}:
            try:
                equipment_uuid = UUID(str(identifier))
            except ValueError:
                _result(normalized, "failed", "Invalid equipment identifier")
                continue
            if verb == "calibrate":
                existing_task = (
                    db.query(models.EquipmentMaintenance)
                    .filter(models.EquipmentMaintenance.equipment_id == equipment_uuid)
                    .filter(models.EquipmentMaintenance.completed_at.is_(None))
                    .order_by(models.EquipmentMaintenance.due_date.asc())
                    .first()
                )
                if existing_task:
                    existing_task.completed_at = now
                    existing_task.description = (
                        existing_task.description
                        or "Calibration resolved via orchestrator"
                    )
                else:
                    db.add(
                        models.EquipmentMaintenance(
                            equipment_id=equipment_uuid,
                            due_date=now,
                            completed_at=now,
                            task_type="calibration",
                            description=f"Calibration confirmed during execution {execution.id}",
                        )
                    )
                _register_lock("equipment", str(equipment_uuid), "released")
                _result(normalized, "executed", "Calibration confirmed and logged")
                continue
            if verb == "maintenance_request":
                maintenance_context = context.get("maintenance") or {}
                equipment_context = {}
                if isinstance(maintenance_context, dict):
                    equipment_context = maintenance_context.get(identifier) or {}
                due_days = equipment_context.get("due_in_days", 7)
                try:
                    due_days = max(1, int(due_days))
                except (TypeError, ValueError):
                    due_days = 7
                due_date = now + timedelta(days=due_days)
                description = equipment_context.get(
                    "description",
                    f"Auto-generated maintenance request for execution {execution.id}",
                )
                db.add(
                    models.EquipmentMaintenance(
                        equipment_id=equipment_uuid,
                        due_date=due_date,
                        task_type="maintenance",
                        description=description,
                    )
                )
                _register_followup(
                    "equipment",
                    str(equipment_uuid),
                    "Maintenance request logged for scheduling",
                    eta=due_date,
                )
                _register_lock("equipment", str(equipment_uuid), "pending")
                _result(normalized, "executed", "Maintenance request submitted")
                continue

        if domain == "compliance" and verb == "approve":
            approval_id = identifier or "unspecified"
            compliance_payload = dict(execution_result.get("compliance") or {})
            approvals = set(str(value) for value in compliance_payload.get("approvals", []))
            approvals.add(str(approval_id))
            compliance_payload["approvals"] = sorted(approvals)
            compliance_payload["updated_at"] = now.isoformat()
            execution_result["compliance"] = compliance_payload
            _register_lock("compliance", str(approval_id), "released")
            _result(normalized, "executed", "Approval recorded for execution gate")
            mutated_execution = True
            continue

        if domain == "notify" and verb == "approver":
            message = (
                f"Approval required: {identifier or 'unspecified'} for execution {execution.id}"
            )
            notification = models.Notification(
                user_id=user.id,
                message=message,
                title="Approval follow-up",
                category="compliance",
                priority="high",
                meta={
                    "execution_id": str(execution.id),
                    "step_index": step_index,
                    "approval": identifier or "unspecified",
                },
            )
            db.add(notification)
            _register_followup(
                "compliance",
                identifier or "approver",
                "Approver notification queued",
            )
            _result(normalized, "scheduled", "Approver notification enqueued")
            continue

        # Default path for unhandled actions
        _register_followup(
            domain or "general",
            identifier or normalized,
            "No automated remediation implemented",
        )
        _result(normalized, "skipped", "Action requires manual intervention")

    execution_result["locks"] = locks_payload
    execution_result["followups"] = followups_payload
    if results:
        remediation_log.append(
            {
                "step_index": step_index,
                "timestamp": now.isoformat(),
                "actions": list(actions),
                "results": [result.model_dump() for result in results],
            }
        )
        execution_result["remediation_log"] = remediation_log
        mutated_execution = True

    if mutated_execution:
        execution.result = execution_result
    if mutated_params:
        execution.params = params

    if results:
        record_execution_event(
            db,
            execution,
            "remediation.execute",
            {
                "step_index": step_index,
                "actions": list(actions),
                "results": [result.model_dump() for result in results],
            },
            user,
        )

    return results


def _store_step_progress(
    execution: models.ProtocolExecution,
    step_index: int,
    update: schemas.ExperimentStepStatusUpdate,
) -> None:
    """Persist step progress metadata and update execution status."""

    # purpose: encapsulate storage of step progression details for reuse across endpoints
    # inputs: execution model, target step index, ExperimentStepStatusUpdate payload
    # outputs: mutates execution.result/status in-place prior to DB flush
    # status: pilot
    execution_result_raw = execution.result if isinstance(execution.result, dict) else {}
    steps_payload = (
        execution_result_raw.get("steps", {})
        if isinstance(execution_result_raw, dict)
        else {}
    )
    steps_payload = dict(steps_payload)
    steps_payload[str(step_index)] = {
        "status": update.status,
        "started_at": _iso_or_none(update.started_at),
        "completed_at": _iso_or_none(update.completed_at),
    }
    execution_result = dict(execution_result_raw)
    execution_result["steps"] = steps_payload

    statuses = {payload.get("status", "pending") for payload in steps_payload.values()}
    if statuses and all(status == "completed" for status in statuses):
        execution.status = "completed"
    elif "in_progress" in statuses or update.status == "in_progress":
        execution.status = "in_progress"

    execution.result = execution_result


def _encode_timeline_cursor(event: models.ExecutionEvent) -> str:
    """Generate opaque cursor token anchored to created_at and sequence."""

    # purpose: support stable pagination for execution timeline queries
    # inputs: execution event row persisted in the database
    # outputs: token string safe for round-trip via API query params
    # status: pilot
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return f"{created_at.isoformat()}|{event.sequence}"


def _parse_timeline_cursor(token: str | None) -> tuple[datetime, int] | None:
    """Decode timeline cursor tokens, returning timestamp and sequence pair."""

    # purpose: safely decode pagination tokens received from clients
    # inputs: raw cursor string from query params
    # outputs: tuple of datetime and sequence or None when invalid
    # status: pilot
    if not token:
        return None
    try:
        timestamp_part, sequence_part = token.split("|", 1)
    except ValueError:
        return None
    timestamp = _coerce_datetime(timestamp_part)
    if timestamp is None:
        return None
    try:
        sequence = int(sequence_part)
    except (TypeError, ValueError):
        return None
    return timestamp, sequence


def _normalize_stream_topics(connection_info: dict[str, Any]) -> list[str]:
    """Derive human friendly telemetry stream names from connection metadata."""

    # purpose: expose instrument channel metadata for live console visualization
    # inputs: connection_info blob stored on equipment records
    # outputs: list[str] representing stream/topic identifiers
    # status: experimental
    candidates = connection_info.get("channels")
    if not candidates:
        candidates = connection_info.get("streams") or connection_info.get("topics")
    if not candidates:
        return []
    if isinstance(candidates, (list, tuple, set)):
        return [str(item) for item in candidates if item is not None]
    if isinstance(candidates, dict):
        return [f"{key}:{value}" for key, value in candidates.items()]
    return [str(candidates)]


def _summarize_reading_payload(data: dict[str, Any]) -> str:
    """Generate a concise string summary for auto-log hydration."""

    # purpose: translate structured telemetry into notebook-friendly prose
    # inputs: latest telemetry data payload stored on EquipmentReading
    # outputs: formatted string summary capturing key-value pairs
    # status: experimental
    fragments: list[str] = []
    for key, value in data.items():
        if isinstance(value, (dict, list, set, tuple)):
            fragments.append(f"{key}={value}")
        else:
            fragments.append(f"{key}={value}")
    return " | ".join(fragments)


def _derive_anomalies(
    equipment: models.Equipment,
    reading: models.EquipmentReading | None,
    topics: Sequence[str],
) -> list[schemas.ExperimentAnomalySignal]:
    """Translate raw telemetry flags into anomaly events."""

    # purpose: surface deviation signals for the experiment console UI
    # inputs: equipment row, latest reading row, candidate stream topics
    # outputs: list of ExperimentAnomalySignal derived from telemetry payload
    # status: experimental
    if not reading or not isinstance(reading.data, dict):
        return []
    data = reading.data or {}
    timestamp = reading.timestamp
    channel = topics[0] if topics else equipment.eq_type or "telemetry"
    events: list[schemas.ExperimentAnomalySignal] = []

    alerts = data.get("alerts")
    if isinstance(alerts, list):
        for raw in alerts:
            if isinstance(raw, dict):
                severity = str(raw.get("severity", "warning")).lower()
                message = str(raw.get("message") or raw)
                channel_override = raw.get("channel")
            else:
                severity = "warning"
                message = str(raw)
                channel_override = None
            normalized = severity if severity in {"info", "warning", "critical"} else "warning"
            events.append(
                schemas.ExperimentAnomalySignal(
                    equipment_id=equipment.id,
                    channel=str(channel_override or channel),
                    message=message,
                    severity=normalized,
                    timestamp=timestamp,
                )
            )

    status_flag = data.get("status")
    if isinstance(status_flag, str):
        normalized = status_flag.lower()
        if normalized not in {"ok", "ready", "nominal"}:
            events.append(
                schemas.ExperimentAnomalySignal(
                    equipment_id=equipment.id,
                    channel=channel,
                    message=f"Status reported as {status_flag}",
                    severity="critical" if normalized in {"error", "fault", "offline"} else "warning",
                    timestamp=timestamp,
                )
            )

    return events


def _collect_equipment_channels(
    db: Session, equipment_ids: list[UUID]
) -> tuple[
    list[schemas.EquipmentTelemetryChannel],
    list[schemas.ExperimentAnomalySignal],
    list[schemas.ExperimentAutoLogEntry],
]:
    """Hydrate telemetry channel metadata and derived artifacts for the console."""

    # purpose: enrich experiment session payloads with live device context
    # inputs: sql session and list of equipment ids tied to execution params
    # outputs: telemetry channels, anomaly events, auto log entry collection
    # status: experimental
    if not equipment_ids:
        return [], [], []

    equipment_rows = (
        db.query(models.Equipment).filter(models.Equipment.id.in_(equipment_ids)).all()
    )
    if not equipment_rows:
        return [], [], []

    readings = (
        db.query(models.EquipmentReading)
        .filter(models.EquipmentReading.equipment_id.in_(equipment_ids))
        .order_by(models.EquipmentReading.equipment_id, models.EquipmentReading.timestamp.desc())
        .all()
    )
    latest_by_id: dict[UUID, models.EquipmentReading] = {}
    for reading in readings:
        if reading.equipment_id not in latest_by_id:
            latest_by_id[reading.equipment_id] = reading

    channels: list[schemas.EquipmentTelemetryChannel] = []
    anomalies: list[schemas.ExperimentAnomalySignal] = []
    auto_logs: list[schemas.ExperimentAutoLogEntry] = []

    for equipment in equipment_rows:
        topics = _normalize_stream_topics(equipment.connection_info or {})
        latest = latest_by_id.get(equipment.id)
        channels.append(
            schemas.EquipmentTelemetryChannel(
                equipment=equipment,
                status=equipment.status,
                stream_topics=topics,
                latest_reading=latest,
            )
        )
        anomalies.extend(_derive_anomalies(equipment, latest, topics))
        if latest and isinstance(latest.data, dict) and latest.data:
            auto_logs.append(
                schemas.ExperimentAutoLogEntry(
                    source=equipment.name,
                    title=f"{equipment.name} telemetry snapshot",
                    body=_summarize_reading_payload(latest.data),
                    created_at=latest.timestamp,
                )
            )

    return channels, anomalies, auto_logs


def _assemble_session(
    db: Session,
    execution: models.ProtocolExecution,
) -> schemas.ExperimentExecutionSessionOut:
    """Construct the aggregated experiment execution payload."""

    # purpose: hydrate experiment execution console state for consumers
    # inputs: active database session, execution model instance
    # outputs: ExperimentExecutionSessionOut ready for API serialization
    # status: production
    template = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == execution.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Linked protocol template not found")

    notebook_entries = (
        db.query(models.NotebookEntry)
        .filter(models.NotebookEntry.execution_id == execution.id)
        .order_by(models.NotebookEntry.created_at.asc())
        .all()
    )

    params = execution.params or {}
    inventory_ids = _parse_uuid_list(params.get("inventory_item_ids", []))
    booking_ids = _parse_uuid_list(params.get("booking_ids", []))
    equipment_ids = _parse_uuid_list(params.get("equipment_ids", []))

    inventory_items = []
    if inventory_ids:
        inventory_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )

    bookings = []
    if booking_ids:
        bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )

    instructions = _extract_steps(template.content)
    gate_context = _prepare_step_gate_context(db, execution, inventory_items, bookings)
    steps = _build_step_states(execution, instructions, gate_context)
    telemetry_channels, anomaly_events, auto_logs = _collect_equipment_channels(
        db, equipment_ids
    )

    recent_events = (
        db.query(models.ExecutionEvent)
        .options(joinedload(models.ExecutionEvent.actor))
        .filter(models.ExecutionEvent.execution_id == execution.id)
        .order_by(
            models.ExecutionEvent.created_at.desc(),
            models.ExecutionEvent.sequence.desc(),
        )
        .limit(10)
        .all()
    )
    timeline_preview = [
        schemas.ExecutionEventOut.model_validate(event) for event in recent_events
    ]

    return schemas.ExperimentExecutionSessionOut(
        execution=execution,
        protocol=template,
        notebook_entries=notebook_entries,
        inventory_items=inventory_items,
        bookings=bookings,
        steps=steps,
        telemetry_channels=telemetry_channels,
        anomaly_events=anomaly_events,
        auto_log_entries=auto_logs,
        timeline_preview=timeline_preview,
    )


@router.post(
    "/sessions",
    response_model=schemas.ExperimentExecutionSessionOut,
)
async def create_execution_session(
    payload: schemas.ExperimentExecutionSessionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a cohesive execution session spanning protocols, notes, and assets."""

    # purpose: initialize structured experiment execution context for console
    # inputs: ExperimentExecutionSessionCreate payload
    # outputs: ExperimentExecutionSessionOut representing fresh session state
    # status: production
    try:
        template_id = UUID(str(payload.template_id))
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail="Invalid template id") from exc

    template = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    params: dict[str, Any] = dict(payload.parameters or {})
    required_variables = template.variables or []
    missing = [var for var in required_variables if var not in params]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required parameters: {', '.join(missing)}",
        )

    inventory_ids = _parse_uuid_list(payload.inventory_item_ids)
    if inventory_ids:
        existing_inventory = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )
        if len(existing_inventory) != len(inventory_ids):
            raise HTTPException(status_code=404, detail="Inventory item not found")

    booking_ids = _parse_uuid_list(payload.booking_ids)
    if booking_ids:
        existing_bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )
        if len(existing_bookings) != len(booking_ids):
            raise HTTPException(status_code=404, detail="Booking not found")

    params["inventory_item_ids"] = [str(item_id) for item_id in inventory_ids]
    params["booking_ids"] = [str(booking_id) for booking_id in booking_ids]

    execution = models.ProtocolExecution(
        template_id=template_id,
        run_by=user.id,
        status="in_progress",
        params=params,
        result={"steps": {}},
    )
    db.add(execution)
    db.flush()

    record_execution_event(
        db,
        execution,
        "session.created",
        {
            "title": payload.title or template.name,
            "template_id": str(template.id),
            "inventory_item_ids": [str(item_id) for item_id in inventory_ids],
            "booking_ids": [str(booking_id) for booking_id in booking_ids],
        },
        user,
    )

    if payload.auto_create_notebook:
        notebook_entry = models.NotebookEntry(
            title=payload.title or f"{template.name} Execution",
            content=f"Auto-created execution log for {template.name}",
            execution_id=execution.id,
            created_by=user.id,
            items=[str(item_id) for item_id in inventory_ids],
            protocols=[str(template.id)],
        )
        db.add(notebook_entry)

    db.commit()
    db.refresh(execution)

    return _assemble_session(db, execution)


@preview_router.get(
    "/{execution_id}/scenarios",
    response_model=schemas.ExperimentScenarioWorkspace,
)
async def list_execution_scenarios(
    execution_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return accessible preview scenarios and available snapshots for an execution."""

    # purpose: power the scientist scenario workspace with persisted simulations
    # inputs: execution identifier path param, authenticated user
    # outputs: ExperimentScenarioWorkspace summarising execution, snapshots, and scenarios
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    team_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, team_ids)

    assigned_template_ids = _resolve_assigned_template_ids(db, template)
    scenario_query = (
        db.query(models.ExperimentScenario)
        .options(
            joinedload(models.ExperimentScenario.snapshot).joinedload(
                models.ExecutionNarrativeWorkflowTemplateSnapshot.template
            ),
            joinedload(models.ExperimentScenario.folder),
        )
        .filter(models.ExperimentScenario.execution_id == execution.id)
        .filter(
            or_(
                models.ExperimentScenario.expires_at.is_(None),
                models.ExperimentScenario.expires_at > datetime.now(timezone.utc),
            )
        )
        .order_by(models.ExperimentScenario.updated_at.desc())
    )
    scenario_rows = scenario_query.all()

    accessible_scenarios: list[schemas.ExperimentScenario] = []
    snapshot_template_ids = set(assigned_template_ids)
    for scenario in scenario_rows:
        if _scenario_accessible(scenario, user, team_ids):
            accessible_scenarios.append(_serialize_scenario(scenario))
            if scenario.snapshot and scenario.snapshot.template_id:
                snapshot_template_ids.add(scenario.snapshot.template_id)

    folder_rows = (
        db.query(models.ExperimentScenarioFolder)
        .filter(models.ExperimentScenarioFolder.execution_id == execution.id)
        .order_by(models.ExperimentScenarioFolder.updated_at.desc())
        .all()
    )

    accessible_folders = [
        _serialize_folder(folder)
        for folder in folder_rows
        if _folder_accessible(folder, user, team_ids)
    ]

    snapshot_rows: list[models.ExecutionNarrativeWorkflowTemplateSnapshot] = []
    if snapshot_template_ids:
        snapshot_rows = (
            db.query(models.ExecutionNarrativeWorkflowTemplateSnapshot)
            .options(
                joinedload(
                    models.ExecutionNarrativeWorkflowTemplateSnapshot.template
                )
            )
            .filter(
                models.ExecutionNarrativeWorkflowTemplateSnapshot.template_id.in_(
                    list(snapshot_template_ids)
                )
            )
            .order_by(
                models.ExecutionNarrativeWorkflowTemplateSnapshot.captured_at.desc()
            )
            .all()
        )

    snapshot_payload: dict[UUID, schemas.ExperimentScenarioSnapshot] = {}
    for snapshot in snapshot_rows:
        snapshot_payload[snapshot.id] = schemas.ExperimentScenarioSnapshot(
            id=snapshot.id,
            template_id=snapshot.template_id,
            template_key=snapshot.template_key,
            version=snapshot.version,
            status=snapshot.status,
            captured_at=snapshot.captured_at,
            captured_by_id=snapshot.captured_by_id,
            template_name=(snapshot.template.name if snapshot.template else None),
        )

    execution_summary = schemas.ExperimentScenarioExecutionSummary(
        id=execution.id,
        template_id=execution.template_id,
        template_name=template.name if template else None,
        template_version=str(template.version) if template and template.version else None,
        run_by_id=execution.run_by,
        status=execution.status,
    )

    return schemas.ExperimentScenarioWorkspace(
        execution=execution_summary,
        snapshots=list(snapshot_payload.values()),
        scenarios=accessible_scenarios,
        folders=accessible_folders,
    )


@preview_router.post(
    "/{execution_id}/scenario-folders",
    response_model=schemas.ExperimentScenarioFolder,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario_folder(
    execution_id: str,
    payload: schemas.ExperimentScenarioFolderCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Persist a collaborative folder for organizing scenarios."""

    # purpose: enable scientists to group preview scenarios for shared review
    # inputs: execution identifier and folder creation payload
    # outputs: ExperimentScenarioFolder schema for the new folder
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    team_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, team_ids)

    visibility = payload.visibility
    team_id = payload.team_id
    if visibility == "team" and team_id is None:
        team_id = template.team_id
    if visibility == "team" and team_id is None:
        raise HTTPException(status_code=400, detail="Team visibility requires a team id")

    folder = models.ExperimentScenarioFolder(
        execution_id=execution.id,
        name=payload.name,
        description=payload.description,
        owner_id=user.id,
        team_id=team_id,
        visibility=visibility,
    )
    db.add(folder)

    record_execution_event(
        db,
        execution,
        "scenario.folder.created",
        {
            "folder_id": str(folder.id),
            "name": folder.name,
            "visibility": folder.visibility,
        },
        user,
    )

    db.commit()
    db.refresh(folder)

    return _serialize_folder(folder)


@preview_router.patch(
    "/{execution_id}/scenario-folders/{folder_id}",
    response_model=schemas.ExperimentScenarioFolder,
)
async def update_scenario_folder(
    execution_id: str,
    folder_id: str,
    payload: schemas.ExperimentScenarioFolderUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update metadata for a scenario folder."""

    # purpose: support renaming and sharing adjustments for scenario folders
    # inputs: execution identifier, folder identifier, update payload
    # outputs: refreshed ExperimentScenarioFolder schema
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        folder_uuid = UUID(folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    folder = (
        db.query(models.ExperimentScenarioFolder)
        .filter(
            models.ExperimentScenarioFolder.id == folder_uuid,
            models.ExperimentScenarioFolder.execution_id == execution.id,
        )
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Scenario folder not found")

    team_ids = _get_user_team_ids(db, user)
    _ensure_execution_access(db, execution, user, team_ids)

    if not (user.is_admin or folder.owner_id == user.id):
        raise HTTPException(status_code=403, detail="Only the owner may update this folder")

    fields_set = getattr(payload, "model_fields_set", set())

    if payload.name is not None:
        folder.name = payload.name
    if payload.description is not None:
        folder.description = payload.description

    if "visibility" in fields_set or "team_id" in fields_set:
        visibility = payload.visibility or folder.visibility
        team_id = payload.team_id if payload.team_id is not None else folder.team_id
        if visibility == "team" and team_id is None:
            team_id = execution.template.team_id if execution.template else None
        if visibility == "team" and team_id is None:
            raise HTTPException(status_code=400, detail="Team visibility requires a team id")
        folder.visibility = visibility
        folder.team_id = team_id

    record_execution_event(
        db,
        execution,
        "scenario.folder.updated",
        {
            "folder_id": str(folder.id),
            "name": folder.name,
            "visibility": folder.visibility,
        },
        user,
    )

    db.add(folder)
    db.commit()
    db.refresh(folder)

    return _serialize_folder(folder)


@preview_router.post(
    "/{execution_id}/scenarios",
    response_model=schemas.ExperimentScenario,
    status_code=status.HTTP_201_CREATED,
)
async def create_execution_scenario(
    execution_id: str,
    payload: schemas.ExperimentScenarioCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Persist a new preview scenario scoped to an execution."""

    # purpose: allow scientists to capture reusable preview configurations
    # inputs: execution identifier path param, scenario creation payload
    # outputs: ExperimentScenario schema for the persisted scenario
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    team_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, team_ids)

    snapshot = db.get(
        models.ExecutionNarrativeWorkflowTemplateSnapshot,
        payload.workflow_template_snapshot_id,
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Workflow template snapshot not found")

    assigned_template_ids = _resolve_assigned_template_ids(db, template)
    if assigned_template_ids and snapshot.template_id not in assigned_template_ids:
        raise HTTPException(
            status_code=403,
            detail="Snapshot is not assigned to this execution context",
        )

    folder = _validate_folder_assignment(
        db,
        execution,
        payload.folder_id,
        user,
        team_ids,
    )
    shared_team_ids = _normalize_shared_team_ids(payload.shared_team_ids)
    expires_at = payload.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    timeline_event = _validate_timeline_event_binding(
        db,
        execution,
        payload.timeline_event_id,
    )

    scenario = models.ExperimentScenario(
        execution_id=execution.id,
        owner_id=user.id,
        team_id=template.team_id,
        workflow_template_snapshot_id=snapshot.id,
        name=payload.name,
        description=payload.description,
        resource_overrides=_prepare_resource_override_payload(
            payload.resource_overrides
        ),
        stage_overrides=_prepare_stage_override_payload(payload.stage_overrides),
        folder_id=folder.id if folder else None,
        is_shared=bool(payload.is_shared or shared_team_ids),
        shared_team_ids=shared_team_ids,
        expires_at=expires_at,
        timeline_event_id=timeline_event.id if timeline_event else None,
    )
    db.add(scenario)

    record_execution_event(
        db,
        execution,
        "scenario.saved",
        {
            "scenario_id": str(scenario.id),
            "snapshot_id": str(snapshot.id),
            "name": payload.name,
            "folder_id": str(folder.id) if folder else None,
            "is_shared": scenario.is_shared,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "timeline_event_id": str(timeline_event.id)
            if timeline_event
            else None,
        },
        user,
    )

    db.commit()
    db.refresh(scenario)

    return _serialize_scenario(scenario)


@preview_router.put(
    "/{execution_id}/scenarios/{scenario_id}",
    response_model=schemas.ExperimentScenario,
)
async def update_execution_scenario(
    execution_id: str,
    scenario_id: str,
    payload: schemas.ExperimentScenarioUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update scenario metadata and overrides."""

    # purpose: support iterative refinement of saved scenarios
    # inputs: execution and scenario identifiers plus update payload
    # outputs: refreshed ExperimentScenario representation
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        scenario_uuid = UUID(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    scenario = (
        db.query(models.ExperimentScenario)
        .filter(
            models.ExperimentScenario.id == scenario_uuid,
            models.ExperimentScenario.execution_id == execution.id,
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    team_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, team_ids)

    if not (user.is_admin or scenario.owner_id == user.id):
        raise HTTPException(status_code=403, detail="Only the owner may update this scenario")

    fields_set = getattr(payload, "model_fields_set", set())

    if payload.name is not None:
        scenario.name = payload.name
    if payload.description is not None:
        scenario.description = payload.description

    if payload.workflow_template_snapshot_id is not None:
        snapshot = db.get(
            models.ExecutionNarrativeWorkflowTemplateSnapshot,
            payload.workflow_template_snapshot_id,
        )
        if not snapshot:
            raise HTTPException(status_code=404, detail="Workflow template snapshot not found")
        assigned_template_ids = _resolve_assigned_template_ids(db, template)
        if assigned_template_ids and snapshot.template_id not in assigned_template_ids:
            raise HTTPException(
                status_code=403,
                detail="Snapshot is not assigned to this execution context",
            )
        scenario.workflow_template_snapshot_id = snapshot.id

    if payload.resource_overrides is not None:
        scenario.resource_overrides = _prepare_resource_override_payload(
            payload.resource_overrides
        )
    if payload.stage_overrides is not None:
        scenario.stage_overrides = _prepare_stage_override_payload(
            payload.stage_overrides
        )

    if "folder_id" in fields_set:
        folder = _validate_folder_assignment(
            db,
            execution,
            payload.folder_id,
            user,
            team_ids,
        )
        scenario.folder_id = folder.id if folder else None
    else:
        folder = scenario.folder

    if "shared_team_ids" in fields_set:
        if payload.shared_team_ids is None:
            scenario.shared_team_ids = []
        else:
            scenario.shared_team_ids = _normalize_shared_team_ids(payload.shared_team_ids)

    if payload.is_shared is not None or "shared_team_ids" in fields_set or "folder_id" in fields_set:
        if payload.is_shared is not None:
            scenario.is_shared = bool(payload.is_shared)
        elif "shared_team_ids" in fields_set:
            scenario.is_shared = bool(scenario.shared_team_ids)

    if "expires_at" in fields_set:
        if payload.expires_at is None:
            scenario.expires_at = None
        else:
            expires_at = payload.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            scenario.expires_at = expires_at

    if "timeline_event_id" in fields_set:
        if payload.timeline_event_id is None:
            scenario.timeline_event_id = None
        else:
            event = _validate_timeline_event_binding(
                db,
                execution,
                payload.timeline_event_id,
            )
            scenario.timeline_event_id = event.id

    if "transfer_owner_id" in fields_set and payload.transfer_owner_id:
        if not (user.is_admin or scenario.owner_id == user.id):
            raise HTTPException(status_code=403, detail="Only the owner may transfer ownership")
        new_owner = db.get(models.User, payload.transfer_owner_id)
        if not new_owner:
            raise HTTPException(status_code=404, detail="New owner not found")
        scenario.owner_id = new_owner.id

    record_execution_event(
        db,
        execution,
        "scenario.updated",
        {
            "scenario_id": str(scenario.id),
            "name": scenario.name,
            "folder_id": str(scenario.folder_id) if scenario.folder_id else None,
            "is_shared": scenario.is_shared,
            "expires_at": scenario.expires_at.isoformat()
            if scenario.expires_at
            else None,
            "timeline_event_id": str(scenario.timeline_event_id)
            if scenario.timeline_event_id
            else None,
        },
        user,
    )

    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return _serialize_scenario(scenario)


@preview_router.post(
    "/{execution_id}/scenarios/{scenario_id}/clone",
    response_model=schemas.ExperimentScenario,
    status_code=status.HTTP_201_CREATED,
)
async def clone_execution_scenario(
    execution_id: str,
    scenario_id: str,
    payload: schemas.ExperimentScenarioCloneRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Clone an existing scenario into a new record owned by the requester."""

    # purpose: enable scientists to branch scenarios without manual re-entry
    # inputs: execution id, source scenario id, optional clone metadata overrides
    # outputs: ExperimentScenario representing the newly cloned scenario
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        scenario_uuid = UUID(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    source = (
        db.query(models.ExperimentScenario)
        .options(
            joinedload(models.ExperimentScenario.snapshot)
            .joinedload(models.ExecutionNarrativeWorkflowTemplateSnapshot.template),
            joinedload(models.ExperimentScenario.folder),
        )
        .filter(
            models.ExperimentScenario.id == scenario_uuid,
            models.ExperimentScenario.execution_id == execution.id,
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Scenario not found")

    team_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, team_ids)

    if not (
        user.is_admin
        or source.owner_id == user.id
        or (source.team_id and source.team_id in team_ids)
    ):
        raise HTTPException(status_code=403, detail="Not authorized to clone this scenario")

    inherited_folder_id: UUID | None = None
    if source.folder_id and _folder_accessible(source.folder, user, team_ids):
        inherited_folder_id = source.folder_id

    cloned = models.ExperimentScenario(
        execution_id=execution.id,
        owner_id=user.id,
        team_id=template.team_id,
        workflow_template_snapshot_id=source.workflow_template_snapshot_id,
        name=payload.name or f"{source.name} Copy",
        description=payload.description if payload.description is not None else source.description,
        resource_overrides=copy.deepcopy(source.resource_overrides or {}),
        stage_overrides=copy.deepcopy(source.stage_overrides or []),
        cloned_from_id=source.id,
        folder_id=inherited_folder_id,
        is_shared=False,
        shared_team_ids=[],
        expires_at=None,
        timeline_event_id=None,
    )
    db.add(cloned)

    record_execution_event(
        db,
        execution,
        "scenario.cloned",
        {
            "scenario_id": str(cloned.id),
            "source_scenario_id": str(source.id),
            "folder_id": str(inherited_folder_id) if inherited_folder_id else None,
        },
        user,
    )

    db.commit()
    db.refresh(cloned)

    return _serialize_scenario(cloned)


@preview_router.delete(
    "/{execution_id}/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_execution_scenario(
    execution_id: str,
    scenario_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Remove a persisted scenario."""

    # purpose: allow scientists to curate scenario workspace storage
    # inputs: execution id and scenario id
    # outputs: empty response with 204 status code on success
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        scenario_uuid = UUID(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    scenario = (
        db.query(models.ExperimentScenario)
        .filter(
            models.ExperimentScenario.id == scenario_uuid,
            models.ExperimentScenario.execution_id == execution.id,
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    team_ids = _get_user_team_ids(db, user)
    _ensure_execution_access(db, execution, user, team_ids)

    if not (user.is_admin or scenario.owner_id == user.id):
        raise HTTPException(status_code=403, detail="Only the owner may delete this scenario")

    record_execution_event(
        db,
        execution,
        "scenario.deleted",
        {
            "scenario_id": str(scenario.id),
            "name": scenario.name,
        },
        user,
    )

    db.delete(scenario)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@preview_router.post(
    "/{execution_id}/preview",
    response_model=schemas.ExperimentPreviewResponse,
)
def preview_experiment_governance(
    execution_id: str,
    payload: schemas.ExperimentPreviewRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Simulate governance ladder outcomes for an experiment execution."""

    # purpose: provide scientist-facing preview of governance impact before publication
    # inputs: execution identifier path param, preview request payload, authenticated user
    # outputs: ExperimentPreviewResponse containing stage insights and narrative preview
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if not execution.template_id:
        raise HTTPException(
            status_code=400,
            detail="Execution missing linked protocol template for preview",
        )

    team_ids = _get_user_team_ids(db, user)
    _ensure_execution_access(db, execution, user, team_ids)

    snapshot = db.get(
        models.ExecutionNarrativeWorkflowTemplateSnapshot,
        payload.workflow_template_snapshot_id,
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Workflow template snapshot not found")
    if snapshot.status != "published":
        raise HTTPException(
            status_code=400,
            detail="Preview requires a published workflow template snapshot",
        )

    baseline_snapshot: models.ExecutionNarrativeWorkflowTemplateSnapshot | None = None
    baseline_template = db.get(models.ExecutionNarrativeWorkflowTemplate, snapshot.template_id)
    if baseline_template and baseline_template.published_snapshot_id:
        baseline_snapshot = db.get(
            models.ExecutionNarrativeWorkflowTemplateSnapshot,
            baseline_template.published_snapshot_id,
        )
    if baseline_snapshot is None:
        baseline_snapshot = snapshot

    snapshot_payload = snapshot.snapshot_payload or {}
    stage_blueprint: list[dict[str, object]] = []
    if isinstance(snapshot_payload, dict):
        blueprint_candidate = snapshot_payload.get("stage_blueprint")
        if isinstance(blueprint_candidate, list):
            stage_blueprint = [
                stage for stage in blueprint_candidate if isinstance(stage, dict)
            ]
    default_stage_sla = None
    if isinstance(snapshot_payload, dict):
        default_stage_sla = snapshot_payload.get("default_stage_sla_hours")
        if not isinstance(default_stage_sla, int):
            default_stage_sla = None

    baseline_payload = baseline_snapshot.snapshot_payload or {}
    baseline_stage_blueprint: list[dict[str, object]] = []
    if isinstance(baseline_payload, dict):
        baseline_blueprint_candidate = baseline_payload.get("stage_blueprint")
        if isinstance(baseline_blueprint_candidate, list):
            baseline_stage_blueprint = [
                stage
                for stage in baseline_blueprint_candidate
                if isinstance(stage, dict)
            ]
    baseline_default_stage_sla = None
    if isinstance(baseline_payload, dict):
        baseline_default_stage_sla = baseline_payload.get("default_stage_sla_hours")
        if not isinstance(baseline_default_stage_sla, int):
            baseline_default_stage_sla = None
    if not baseline_stage_blueprint:
        baseline_stage_blueprint = stage_blueprint
    if baseline_default_stage_sla is None:
        baseline_default_stage_sla = default_stage_sla

    params = execution.params or {}
    inventory_ids = _parse_uuid_list(params.get("inventory_item_ids", []))
    booking_ids = _parse_uuid_list(params.get("booking_ids", []))

    inventory_items = []
    if inventory_ids:
        inventory_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )
    bookings = []
    if booking_ids:
        bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )

    instructions = _extract_steps(template.content)
    gate_context = _prepare_step_gate_context(db, execution, inventory_items, bookings)
    resource_warnings = _apply_preview_resource_overrides(
        gate_context, payload.resource_overrides
    )
    steps = _build_step_states(execution, instructions, gate_context)

    generated_at = datetime.now(timezone.utc)
    raw_stage_overrides = simulation.normalize_stage_overrides(payload.stage_overrides)
    stage_overrides: dict[int, dict[str, Any]] = {}
    total_stages = len(stage_blueprint)
    for index, override in raw_stage_overrides.items():
        if index < 0 or index >= total_stages:
            resource_warnings.append(
                f"Stage override for index {index} ignored; blueprint has {total_stages} stages"
            )
            continue
        stage_overrides[index] = override

    override_user_ids = {
        value
        for config in stage_overrides.values()
        for value in (config.get("assignee_id"), config.get("delegate_id"))
        if isinstance(value, UUID)
    }
    if override_user_ids:
        known_users = (
            db.query(models.User)
            .filter(models.User.id.in_(list(override_user_ids)))
            .all()
        )
        found_ids = {user.id for user in known_users}
        for missing_id in sorted(override_user_ids - found_ids):
            resource_warnings.append(
                f"User override {missing_id} not found; preview uses placeholder"
            )

    step_requirements = gate_context.get("step_requirements")
    baseline_results = simulation.build_stage_simulation(
        baseline_stage_blueprint,
        default_stage_sla_hours=baseline_default_stage_sla,
        stage_overrides={},
        step_states=steps,
        step_requirements=step_requirements,
        generated_at=generated_at,
    )
    comparison_results = simulation.build_stage_simulation(
        stage_blueprint,
        default_stage_sla_hours=default_stage_sla,
        stage_overrides=stage_overrides,
        step_states=steps,
        step_requirements=step_requirements,
        generated_at=generated_at,
    )

    baseline_map: dict[int, simulation.StageSimulationSnapshot] = {
        entry.index: entry.baseline for entry in baseline_results
    }

    insights: list[schemas.ExperimentPreviewStageInsight] = []
    for comparison in comparison_results:
        simulated = comparison.simulated
        baseline_snapshot_state = baseline_map.get(comparison.index)
        baseline_blockers = (
            list(baseline_snapshot_state.blockers)
            if baseline_snapshot_state
            else []
        )
        simulated_blockers = list(simulated.blockers)
        baseline_blocker_set = {blocker for blocker in baseline_blockers}
        simulated_blocker_set = {blocker for blocker in simulated_blockers}
        delta_new_blockers = [
            blocker for blocker in simulated_blockers if blocker not in baseline_blocker_set
        ]
        delta_resolved_blockers = [
            blocker for blocker in baseline_blockers if blocker not in simulated_blocker_set
        ]
        delta_status = None
        if baseline_snapshot_state:
            if baseline_snapshot_state.status == simulated.status:
                delta_status = "unchanged"
            elif simulated.status == "ready":
                delta_status = "cleared"
            else:
                delta_status = "regressed"

        delta_sla_hours = None
        if (
            baseline_snapshot_state
            and baseline_snapshot_state.sla_hours is not None
            and simulated.sla_hours is not None
        ):
            delta_sla_hours = simulated.sla_hours - baseline_snapshot_state.sla_hours

        delta_projected_due_minutes = None
        if (
            baseline_snapshot_state
            and baseline_snapshot_state.projected_due_at
            and simulated.projected_due_at
        ):
            delta_seconds = (
                simulated.projected_due_at - baseline_snapshot_state.projected_due_at
            ).total_seconds()
            delta_projected_due_minutes = int(delta_seconds // 60)

        status_value = simulated.status if simulated.status in {"ready", "blocked"} else "ready"
        insights.append(
            schemas.ExperimentPreviewStageInsight(
                index=comparison.index,
                name=comparison.name,
                required_role=comparison.required_role,
                status=status_value,
                sla_hours=simulated.sla_hours,
                projected_due_at=simulated.projected_due_at,
                blockers=simulated_blockers,
                required_actions=list(simulated.required_actions),
                auto_triggers=list(simulated.auto_triggers),
                assignee_id=simulated.assignee_id,
                delegate_id=simulated.delegate_id,
                mapped_step_indexes=list(comparison.mapped_step_indexes),
                gate_keys=list(comparison.gate_keys),
                baseline_status=(
                    baseline_snapshot_state.status if baseline_snapshot_state else None
                ),
                baseline_sla_hours=(
                    baseline_snapshot_state.sla_hours if baseline_snapshot_state else None
                ),
                baseline_projected_due_at=(
                    baseline_snapshot_state.projected_due_at
                    if baseline_snapshot_state
                    else None
                ),
                baseline_assignee_id=(
                    baseline_snapshot_state.assignee_id
                    if baseline_snapshot_state
                    else None
                ),
                baseline_delegate_id=(
                    baseline_snapshot_state.delegate_id
                    if baseline_snapshot_state
                    else None
                ),
                baseline_blockers=baseline_blockers,
                delta_status=delta_status,
                delta_sla_hours=delta_sla_hours,
                delta_projected_due_minutes=delta_projected_due_minutes,
                delta_new_blockers=delta_new_blockers,
                delta_resolved_blockers=delta_resolved_blockers,
            )
        )

    narrative_preview = render_preview_narrative(
        execution,
        insights,
        template_snapshot=snapshot_payload,
    )

    audit_entry = models.GovernanceTemplateAuditLog(
        template_id=snapshot.template_id,
        snapshot_id=snapshot.id,
        actor_id=user.id,
        action="template.preview.generated",
        detail={
            "execution_id": str(exec_uuid),
            "stage_count": len(insights),
            "blocked_stage_count": sum(1 for result in insights if result.status == "blocked"),
            "override_indexes": sorted(stage_overrides.keys()),
            "warnings": resource_warnings,
        },
    )
    db.add(audit_entry)
    analytics_payload = _compose_preview_analytics_payload(
        insights,
        generated_at,
        snapshot,
        baseline_snapshot,
        stage_overrides,
        resource_warnings,
    )
    record_execution_event(
        db,
        execution,
        "governance.preview.summary",
        analytics_payload,
        user,
    )
    db.commit()

    template_name = snapshot_payload.get("name") if isinstance(snapshot_payload, dict) else None
    template_version = None
    if isinstance(snapshot_payload, dict):
        version_candidate = snapshot_payload.get("version")
        if isinstance(version_candidate, int):
            template_version = version_candidate

    return schemas.ExperimentPreviewResponse(
        execution_id=exec_uuid,
        snapshot_id=snapshot.id,
        baseline_snapshot_id=baseline_snapshot.id if baseline_snapshot else None,
        generated_at=generated_at,
        template_name=template_name,
        template_version=template_version,
        stage_insights=insights,
        narrative_preview=narrative_preview,
        resource_warnings=resource_warnings,
    )


@router.post(
    "/sessions/{execution_id}/steps/{step_index}/advance",
    response_model=schemas.ExperimentExecutionSessionOut,
)
async def advance_step_status(
    execution_id: str,
    step_index: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Attempt to advance a step using orchestration gates."""

    # purpose: provide rule-driven progression that respects resource readiness
    # inputs: execution identifier, target step index
    # outputs: ExperimentExecutionSessionOut reflecting any progression or blockers
    # status: pilot
    if step_index < 0:
        raise HTTPException(status_code=400, detail="Step index must be non-negative")

    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    template = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == execution.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Linked protocol template not found")

    params = execution.params or {}
    inventory_ids = _parse_uuid_list(params.get("inventory_item_ids", []))
    inventory_items = []
    if inventory_ids:
        inventory_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )

    booking_ids = _parse_uuid_list(params.get("booking_ids", []))
    bookings = []
    if booking_ids:
        bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )

    instructions = _extract_steps(template.content)
    if step_index >= len(instructions):
        raise HTTPException(status_code=404, detail="Step not found for template")

    gate_context = _prepare_step_gate_context(db, execution, inventory_items, bookings)
    step_states = _build_step_states(execution, instructions, gate_context)
    target_state = step_states[step_index]

    if target_state.blocked_reason and target_state.status == "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Step is blocked by orchestration rules",
                "blocked_reason": target_state.blocked_reason,
                "required_actions": target_state.required_actions,
                "auto_triggers": target_state.auto_triggers,
            },
        )

    if target_state.status not in {"pending", "in_progress"}:
        return _assemble_session(db, execution)

    now = datetime.now(timezone.utc)
    if target_state.status == "pending":
        update_payload = schemas.ExperimentStepStatusUpdate(
            status="in_progress",
            started_at=now,
            completed_at=None,
        )
    else:
        update_payload = schemas.ExperimentStepStatusUpdate(
            status="completed",
            started_at=target_state.started_at,
            completed_at=now,
        )

    _store_step_progress(execution, step_index, update_payload)

    record_execution_event(
        db,
        execution,
        "step.transition",
        {
            "step_index": step_index,
            "instruction": instructions[step_index],
            "from_status": target_state.status,
            "to_status": update_payload.status,
            "auto": True,
        },
        user,
    )

    db.add(execution)
    db.commit()
    db.refresh(execution)

    return _assemble_session(db, execution)


@router.post(
    "/sessions/{execution_id}/steps/{step_index}/remediate",
    response_model=schemas.ExperimentRemediationResponse,
)
async def remediate_step_blockers(
    execution_id: str,
    step_index: int,
    payload: schemas.ExperimentRemediationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Execute orchestrator-driven remediation and return refreshed session state."""

    # purpose: close orchestration feedback loop by invoking transactional remediation
    # inputs: execution identifier, target step index, remediation request payload
    # outputs: ExperimentRemediationResponse with execution session and action outcomes
    # status: pilot
    if step_index < 0:
        raise HTTPException(status_code=400, detail="Step index must be non-negative")

    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    template = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == execution.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Linked protocol template not found")

    params = execution.params or {}
    inventory_ids = _parse_uuid_list(params.get("inventory_item_ids", []))
    booking_ids = _parse_uuid_list(params.get("booking_ids", []))

    inventory_items = []
    if inventory_ids:
        inventory_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )

    bookings = []
    if booking_ids:
        bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )

    instructions = _extract_steps(template.content)
    if step_index >= len(instructions):
        raise HTTPException(status_code=404, detail="Step not found for template")

    gate_context = _prepare_step_gate_context(db, execution, inventory_items, bookings)
    step_states = _build_step_states(execution, instructions, gate_context)
    target_state = step_states[step_index]

    requested_actions = list(payload.actions or [])
    if payload.auto:
        requested_actions = list(target_state.auto_triggers)
        if not requested_actions:
            requested_actions = list(target_state.required_actions)
    elif not requested_actions:
        requested_actions = list(target_state.required_actions) + list(
            target_state.auto_triggers
        )

    ordered_actions: list[str] = []
    seen: set[str] = set()
    for action in requested_actions:
        normalized = (action or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered_actions.append(normalized)

    results = _apply_remediation_actions(
        db,
        execution,
        step_index,
        ordered_actions,
        gate_context,
        user,
        payload.context,
    )

    db.add(execution)
    db.commit()
    db.refresh(execution)

    refreshed = _assemble_session(db, execution)
    return schemas.ExperimentRemediationResponse(session=refreshed, results=results)


@router.get(
    "/sessions/{execution_id}",
    response_model=schemas.ExperimentExecutionSessionOut,
)
async def get_execution_session(
    execution_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Retrieve the unified view for a specific execution."""

    # purpose: expose aggregated execution data for the experiment console
    # inputs: execution identifier path parameter
    # outputs: ExperimentExecutionSessionOut containing current state
    # status: production
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return _assemble_session(db, execution)


@router.get(
    "/sessions/{execution_id}/timeline",
    response_model=schemas.ExperimentTimelinePage,
)
async def get_execution_timeline(
    execution_id: str,
    limit: int = 50,
    cursor: str | None = None,
    event_types: str | None = None,
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    """Return paginated execution events for timeline rendering."""

    # purpose: expose durable experiment narrative for UI timeline surfaces
    # inputs: execution identifier, optional limit/cursor and filters
    # outputs: ExperimentTimelinePage containing ordered events and pagination token
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    max_page = min(max(limit, 1), 200)
    query = (
        db.query(models.ExecutionEvent)
        .options(joinedload(models.ExecutionEvent.actor))
        .filter(models.ExecutionEvent.execution_id == exec_uuid)
    )

    if event_types:
        normalized_types = {
            value.strip() for value in event_types.split(",") if value.strip()
        }
        if normalized_types:
            query = query.filter(models.ExecutionEvent.event_type.in_(normalized_types))

    cursor_params = _parse_timeline_cursor(cursor)
    if cursor_params:
        cursor_timestamp, cursor_sequence = cursor_params
        query = query.filter(
            or_(
                models.ExecutionEvent.created_at < cursor_timestamp,
                and_(
                    models.ExecutionEvent.created_at == cursor_timestamp,
                    models.ExecutionEvent.sequence < cursor_sequence,
                ),
            )
        )

    rows = (
        query.order_by(
            models.ExecutionEvent.created_at.desc(),
            models.ExecutionEvent.sequence.desc(),
        )
        .limit(max_page + 1)
        .all()
    )

    events = rows[:max_page]
    next_cursor = None
    if len(rows) > max_page and events:
        anchor = events[-1]
        next_cursor = _encode_timeline_cursor(anchor)

    serialized = [
        schemas.ExecutionEventOut.model_validate(event)
        for event in events
    ]

    return schemas.ExperimentTimelinePage(events=serialized, next_cursor=next_cursor)


@router.get(
    "/governance/timeline",
    response_model=schemas.GovernanceDecisionTimelinePage,
)
async def get_governance_decision_timeline(
    execution_id: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return unified governance decision feed for experiment console."""

    # purpose: expose composite governance timeline blending overrides, baselines, and analytics
    # inputs: optional execution filter, pagination params, authenticated user
    # outputs: GovernanceDecisionTimelinePage with incremental pagination cursor
    # status: pilot

    membership_ids = _get_user_team_ids(db, user)
    execution_scope: list[UUID] = []

    if execution_id:
        try:
            exec_uuid = UUID(execution_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid execution id") from exc
        execution = db.get(models.ProtocolExecution, exec_uuid)
        template = _ensure_execution_access(db, execution, user, membership_ids)
        execution_scope = [exec_uuid]
        if template.team_id:
            membership_ids = {template.team_id} if not user.is_admin else {template.team_id}

    page = load_governance_decision_timeline(
        db,
        user,
        membership_ids=membership_ids,
        execution_ids=execution_scope,
        cursor=cursor,
        limit=limit,
    )
    return page


@router.get("/governance/timeline/stream")
async def stream_governance_timeline(
    request: Request,
    execution_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream real-time lock lifecycle and cooldown telemetry via SSE."""

    # purpose: hydrate experiment console with live reversal locks and cooldown ticks
    # inputs: execution identifier, authenticated request context
    # outputs: streaming response yielding SSE formatted events
    # status: pilot
    try:
        execution_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = db.get(models.ProtocolExecution, execution_uuid)
    membership_ids = _get_user_team_ids(db, user)
    template = _ensure_execution_access(db, execution, user, membership_ids)
    if template.team_id and not user.is_admin:
        membership_ids = {template.team_id}

    overrides = (
        db.query(models.GovernanceOverrideAction)
        .options(
            joinedload(models.GovernanceOverrideAction.reversal_lock_actor),
            joinedload(models.GovernanceOverrideAction.reversal_event),
        )
        .filter(models.GovernanceOverrideAction.execution_id == execution_uuid)
        .order_by(models.GovernanceOverrideAction.created_at.asc())
        .all()
    )

    now = datetime.now(timezone.utc)
    lock_state: dict[str, dict[str, Any]] = {}
    channels: list[str] = []
    for record in overrides:
        snapshot = _serialize_override_lock_snapshot(record, now=now)
        lock_state[snapshot["override_id"]] = snapshot
        channels.append(f"governance:override:{snapshot['override_id']}:locks")

    async def event_iterator() -> AsyncIterator[str]:
        redis_conn = await pubsub.get_redis()
        pubsub_conn = redis_conn.pubsub()
        if channels:
            await pubsub_conn.subscribe(*channels)
        initial_payload = {
            "type": "snapshot",
            "execution_id": str(execution_uuid),
            "locks": list(lock_state.values()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        yield _render_sse_payload(initial_payload)
        last_tick = datetime.now(timezone.utc)
        keepalive_at = datetime.now(timezone.utc)
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = None
                if channels:
                    message = await pubsub_conn.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message.get("data"))
                    except (TypeError, json.JSONDecodeError):  # pragma: no cover - defensive
                        payload = None
                    if isinstance(payload, dict):
                        override_id = payload.get("override_id")
                        if override_id:
                            snapshot = lock_state.setdefault(
                                override_id,
                                {
                                    "override_id": override_id,
                                    "recommendation_id": payload.get("recommendation_id"),
                                    "execution_id": str(execution_uuid),
                                    "execution_hash": payload.get("execution_hash"),
                                    "lock": None,
                                    "cooldown": {
                                        "expires_at": None,
                                        "window_minutes": None,
                                        "remaining_seconds": None,
                                    },
                                },
                            )
                            now_tick = datetime.now(timezone.utc)
                            _apply_lock_event_state(snapshot, {"lock_event": payload}, now=now_tick)
                            cooldown_section = snapshot.get("cooldown") or {}
                            expires_at = _parse_iso_datetime(
                                cooldown_section.get("expires_at")
                            )
                            cooldown_section["remaining_seconds"] = _calculate_remaining_seconds(
                                expires_at, now=now_tick
                            )
                            snapshot["cooldown"] = cooldown_section
                            event_payload = {
                                "type": "lock_event",
                                "execution_id": str(execution_uuid),
                                "override_id": override_id,
                                "lock_state": snapshot,
                                "event": payload,
                                "generated_at": now_tick.isoformat(),
                            }
                            yield _render_sse_payload(event_payload)
                now_tick = datetime.now(timezone.utc)
                if (now_tick - last_tick).total_seconds() >= 1:
                    cooldown_updates: list[dict[str, Any]] = []
                    for snapshot in lock_state.values():
                        cooldown_section = snapshot.get("cooldown")
                        if not cooldown_section:
                            continue
                        expires_at = _parse_iso_datetime(
                            cooldown_section.get("expires_at")
                        )
                        remaining = _calculate_remaining_seconds(expires_at, now=now_tick)
                        if remaining is None:
                            continue
                        cooldown_section["remaining_seconds"] = remaining
                        if remaining >= 0:
                            cooldown_updates.append(
                                {
                                    "override_id": snapshot["override_id"],
                                    "remaining_seconds": remaining,
                                    "expires_at": cooldown_section.get("expires_at"),
                                }
                            )
                    if cooldown_updates:
                        tick_payload = {
                            "type": "cooldown_tick",
                            "execution_id": str(execution_uuid),
                            "cooldowns": cooldown_updates,
                            "generated_at": now_tick.isoformat(),
                        }
                        yield _render_sse_payload(tick_payload)
                    last_tick = now_tick
                if (now_tick - keepalive_at).total_seconds() >= 15:
                    yield ": keep-alive\n\n"
                    keepalive_at = now_tick
                await asyncio.sleep(0.25)
        finally:
            if channels:
                await pubsub_conn.unsubscribe(*channels)
            await pubsub_conn.close()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        event_iterator(), media_type="text/event-stream", headers=headers
    )


@router.post(
    "/sessions/{execution_id}/exports/narrative",
    response_model=schemas.ExecutionNarrativeExport,
)
async def create_execution_narrative_export(
    execution_id: str,
    request: schemas.ExecutionNarrativeExportRequest | None = None,
    dry_run: bool = Query(
        default=False,
        description="Perform guardrail checks without enqueuing packaging",
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Generate and return a Markdown narrative for a protocol execution."""

    # purpose: expose compliance-ready narrative export for experiment console
    # inputs: execution identifier path parameter, authenticated user
    # outputs: ExecutionNarrativeExport payload containing Markdown content
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    template = None
    if execution.template_id:
        template = (
            db.query(models.ProtocolTemplate)
            .filter(models.ProtocolTemplate.id == execution.template_id)
            .first()
        )

    events = (
        db.query(models.ExecutionEvent)
        .options(joinedload(models.ExecutionEvent.actor))
        .filter(models.ExecutionEvent.execution_id == exec_uuid)
        .order_by(
            models.ExecutionEvent.created_at.asc(),
            models.ExecutionEvent.sequence.asc(),
        )
        .all()
    )
    event_map = {event.id: event for event in events}

    payload = request or schemas.ExecutionNarrativeExportRequest()
    narrative = render_execution_narrative(execution, events, template=template)
    generated_at = datetime.now(timezone.utc)

    existing_count = (
        db.query(func.count(models.ExecutionNarrativeExport.id))
        .filter(models.ExecutionNarrativeExport.execution_id == exec_uuid)
        .scalar()
        or 0
    )

    template_record: models.ExecutionNarrativeWorkflowTemplate | None = None
    snapshot_record: models.ExecutionNarrativeWorkflowTemplateSnapshot | None = None
    if payload.workflow_template_snapshot_id:
        snapshot_record = (
            db.query(models.ExecutionNarrativeWorkflowTemplateSnapshot)
            .filter(
                models.ExecutionNarrativeWorkflowTemplateSnapshot.id
                == payload.workflow_template_snapshot_id
            )
            .first()
        )
        if not snapshot_record:
            raise HTTPException(status_code=404, detail="Workflow template snapshot not found")
        template_record = snapshot_record.template
        if not template_record:
            raise HTTPException(status_code=404, detail="Workflow template not found")
    if payload.workflow_template_id:
        template_record = template_record or (
            db.query(models.ExecutionNarrativeWorkflowTemplate)
            .filter(
                models.ExecutionNarrativeWorkflowTemplate.id
                == payload.workflow_template_id
            )
            .first()
        )
        if not template_record:
            raise HTTPException(status_code=404, detail="Workflow template not found")
        if not snapshot_record:
            raise HTTPException(
                status_code=400,
                detail="Workflow template exports require a published snapshot",
            )
        if snapshot_record.template_id != template_record.id:
            raise HTTPException(
                status_code=400,
                detail="Snapshot does not belong to supplied workflow template",
            )

    export_record = models.ExecutionNarrativeExport(
        execution_id=exec_uuid,
        version=existing_count + 1,
        format="markdown",
        content=narrative,
        event_count=len(events),
        generated_at=generated_at,
        requested_by_id=user.id,
        notes=payload.notes,
    )
    export_record.meta = payload.metadata or {}
    export_record.workflow_template_id = payload.workflow_template_id
    if snapshot_record:
        export_record.workflow_template_snapshot_id = snapshot_record.id
    export_record.requested_by = user

    stage_blueprints: list[schemas.ExecutionNarrativeApprovalStageDefinition] = []
    template_snapshot: Dict[str, Any] = {}

    if payload.approval_stages:
        stage_blueprints = list(payload.approval_stages)

    if snapshot_record:
        if snapshot_record.status != "published":
            raise HTTPException(
                status_code=400,
                detail="Only published snapshots can seed exports",
            )
        if template_record.status != "published":
            raise HTTPException(
                status_code=409,
                detail="Workflow template must be published",
            )
        if stage_blueprints:
            raise HTTPException(
                status_code=400,
                detail="Published templates cannot be overridden during export",
            )
        template_snapshot = snapshot_record.snapshot_payload or {}
        export_record.workflow_template_key = template_record.template_key
        export_record.workflow_template_version = template_record.version
        export_record.workflow_template_snapshot = template_snapshot

        snapshot_stages = template_snapshot.get("stage_blueprint", [])
        for stage_data in snapshot_stages:
            if not isinstance(stage_data, dict):
                raise HTTPException(
                    status_code=422,
                    detail="Snapshot stage blueprint must be an object",
                )
            stage_payload: dict[str, Any] = dict(stage_data)
            stage_payload.setdefault(
                "sla_hours",
                stage_payload.get("sla_hours")
                or template_snapshot.get("default_stage_sla_hours"),
            )
            stage_payload.setdefault(
                "metadata",
                stage_payload.get("metadata") or {},
            )
            try:
                resolved_stage = (
                    schemas.ExecutionNarrativeApprovalStageDefinition.model_validate(
                        stage_payload
                    )
                )
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid stage blueprint in workflow snapshot",
                ) from exc
            stage_blueprints.append(resolved_stage)
    elif template_record:
        raise HTTPException(
            status_code=400,
            detail="Workflow template exports require a snapshot reference",
        )

    if not stage_blueprints:
        stage_blueprints = [
            schemas.ExecutionNarrativeApprovalStageDefinition(
                required_role="approver",
            )
        ]
    else:
        export_record.workflow_template_snapshot = template_snapshot or {}

    referenced_user_ids: set[UUID] = set()
    for stage_def in stage_blueprints:
        if stage_def.assignee_id:
            referenced_user_ids.add(stage_def.assignee_id)
        if stage_def.delegate_id:
            referenced_user_ids.add(stage_def.delegate_id)

    resolved_users: dict[UUID, models.User] = {}
    if referenced_user_ids:
        candidates = (
            db.query(models.User)
            .filter(models.User.id.in_(list(referenced_user_ids)))
            .all()
        )
        resolved_users = {candidate.id: candidate for candidate in candidates}
        missing = referenced_user_ids.difference(resolved_users.keys())
        if missing:
            raise HTTPException(
                status_code=404,
                detail="Approval stage references unknown users",
            )

    approval_ladders.initialise_export_ladder(
        export_record,
        stage_blueprints,
        resolved_users,
        now=generated_at,
    )

    def _resolve_event(event_id: UUID) -> models.ExecutionEvent:
        event = event_map.get(event_id)
        if not event:
            event = (
                db.query(models.ExecutionEvent)
                .options(joinedload(models.ExecutionEvent.actor))
                .filter(
                    models.ExecutionEvent.id == event_id,
                    models.ExecutionEvent.execution_id == exec_uuid,
                )
                .first()
            )
        if not event:
            raise HTTPException(
                status_code=404,
                detail="Referenced timeline event not found for export attachment",
            )
        return event

    attachments_summary: list[dict[str, Any]] = []
    for attachment in payload.attachments:
        evidence_type = attachment.type or "timeline_event"
        evidence_context = dict(attachment.context or {})
        if evidence_type in {
            "timeline_event",
            "analytics_snapshot",
            "qc_metric",
            "remediation_report",
        }:
            event = _resolve_event(attachment.reference_id)
            payload_snapshot = event.payload or {}
            base_snapshot = {
                "event_type": event.event_type,
                "payload": payload_snapshot,
                "created_at": event.created_at.isoformat(),
                "actor_id": str(event.actor_id) if event.actor_id else None,
            }
            if evidence_type == "analytics_snapshot":
                metrics = payload_snapshot.get("metrics") if isinstance(payload_snapshot, dict) else None
                if isinstance(metrics, dict):
                    base_snapshot["metric_rollup"] = {
                        "count": len(metrics),
                        "keys": sorted(metrics.keys()),
                    }
            if evidence_type == "qc_metric":
                readings = payload_snapshot.get("readings") if isinstance(payload_snapshot, dict) else None
                if isinstance(readings, list):
                    numeric_values = [r.get("value") for r in readings if isinstance(r, dict) and isinstance(r.get("value"), (int, float))]
                    if numeric_values:
                        base_snapshot["readings_summary"] = {
                            "min": min(numeric_values),
                            "max": max(numeric_values),
                            "avg": sum(numeric_values) / len(numeric_values),
                        }
            if evidence_type == "remediation_report":
                actions = payload_snapshot.get("actions") if isinstance(payload_snapshot, dict) else None
                if isinstance(actions, list):
                    base_snapshot["actions"] = actions
            evidence = models.ExecutionNarrativeExportAttachment(
                evidence_type=evidence_type,
                reference_id=event.id,
                label=attachment.label,
                snapshot=base_snapshot,
                hydration_context=evidence_context,
            )
            export_record.attachments.append(evidence)
        elif evidence_type == "notebook_entry":
            entry = (
                db.query(models.NotebookEntry)
                .filter(models.NotebookEntry.id == attachment.reference_id)
                .first()
            )
            if not entry:
                raise HTTPException(
                    status_code=404,
                    detail="Referenced notebook entry not found for export attachment",
                )
            author = None
            if entry.created_by:
                author = (
                    db.query(models.User)
                    .filter(models.User.id == entry.created_by)
                    .first()
                )
            preview = entry.content[:500] if entry.content else ""
            if preview and len(entry.content) > 500:
                preview = f"{preview}…"
            notebook_snapshot: dict[str, Any] = {
                "title": entry.title,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                "author_id": str(entry.created_by) if entry.created_by else None,
                "author_name": author.full_name if author else None,
                "preview": preview,
            }
            evidence = models.ExecutionNarrativeExportAttachment(
                evidence_type="notebook_entry",
                reference_id=entry.id,
                label=attachment.label or entry.title,
                snapshot=notebook_snapshot,
                hydration_context=evidence_context,
            )
            export_record.attachments.append(evidence)
        elif evidence_type == "file":
            file_obj = (
                db.query(models.File)
                .filter(models.File.id == attachment.reference_id)
                .first()
            )
            if not file_obj:
                raise HTTPException(
                    status_code=404,
                    detail="Referenced file attachment not found",
                )
            evidence = models.ExecutionNarrativeExportAttachment(
                evidence_type="file",
                reference_id=file_obj.id,
                file_id=file_obj.id,
                label=attachment.label or file_obj.filename,
                snapshot={
                    "filename": file_obj.filename,
                    "file_type": file_obj.file_type,
                    "file_size": file_obj.file_size,
                },
                hydration_context=evidence_context,
            )
            evidence.file = file_obj
            export_record.attachments.append(evidence)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type '{evidence_type}'",
            )

    db.add(export_record)
    db.flush()

    if export_record.current_stage:
        stage = export_record.current_stage
        record_execution_event(
            db,
            execution,
            "narrative_export.approval.stage_started",
            {
                "export_id": str(export_record.id),
                "stage_id": str(stage.id),
                "sequence_index": stage.sequence_index,
                "required_role": stage.required_role,
                "assignee_id": str(stage.assignee_id) if stage.assignee_id else None,
                "due_at": stage.due_at.isoformat() if stage.due_at else None,
            },
            actor=user,
        )
        db.flush()

    attachments_summary = [
        {
            "type": record.evidence_type,
            "reference_id": str(record.reference_id),
            "label": record.label,
            "context": record.hydration_context or {},
        }
        for record in export_record.attachments
    ]

    if snapshot_record:
        audit_entry = models.GovernanceTemplateAuditLog(
            template_id=snapshot_record.template_id,
            snapshot_id=snapshot_record.id,
            actor_id=user.id,
            action="export.snapshot.bound",
            detail={
                "export_id": str(export_record.id),
                "execution_id": str(exec_uuid),
            },
        )
        db.add(audit_entry)

    record_execution_event(
        db,
        execution,
        "narrative_export.created",
        {
            "format": export_record.format,
            "generated_at": generated_at.isoformat(),
            "event_count": export_record.event_count,
            "export_id": str(export_record.id),
            "version": export_record.version,
            "approval_status": export_record.approval_status,
            "attachments": attachments_summary,
        },
        actor=user,
    )
    db.commit()

    db.refresh(export_record)

    queued_packaging = approval_ladders.dispatch_export_for_packaging(
        db,
        export=export_record,
        actor=user,
        enqueue=enqueue_narrative_export_packaging,
        dry_run=dry_run,
    )
    db.commit()

    if queued_packaging:
        db.refresh(export_record)

    export_with_relations = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            ),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(models.ExecutionNarrativeExport.id == export_record.id)
        .first()
    )

    if not export_with_relations:
        raise HTTPException(status_code=500, detail="Failed to persist narrative export")

    response_payload = _build_export_payload(db, export_with_relations)
    if response_payload.artifact_status == "ready" and response_payload.artifact_file:
        response_payload.artifact_download_path = _build_artifact_download_path(
            response_payload.execution_id, response_payload.id
        )
        try:
            response_payload.artifact_signed_url = generate_signed_download_url(
                response_payload.artifact_file.storage_path
            )
        except FileNotFoundError:
            response_payload.artifact_signed_url = None
    else:
        response_payload.artifact_download_path = None
        response_payload.artifact_signed_url = None

    return response_payload


@router.get(
    "/sessions/{execution_id}/exports/narrative",
    response_model=schemas.ExecutionNarrativeExportHistory,
)
async def list_execution_narrative_exports(
    execution_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return persisted narrative exports for a given execution."""

    # purpose: surface export history for experiment console clients
    # inputs: execution identifier path parameter, authenticated user
    # outputs: chronological ExecutionNarrativeExport collection
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    del user

    exports = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            ),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(models.ExecutionNarrativeExport.execution_id == exec_uuid)
        .order_by(models.ExecutionNarrativeExport.generated_at.desc())
        .all()
    )

    serialized: list[schemas.ExecutionNarrativeExport] = []
    for export in exports:
        payload = _build_export_payload(db, export)
        if payload.artifact_status == "ready" and payload.artifact_file:
            payload.artifact_download_path = _build_artifact_download_path(
                payload.execution_id, payload.id
            )
            try:
                payload.artifact_signed_url = generate_signed_download_url(
                    payload.artifact_file.storage_path
                )
            except FileNotFoundError:
                payload.artifact_signed_url = None
        else:
            payload.artifact_download_path = None
            payload.artifact_signed_url = None
        serialized.append(payload)
    return schemas.ExecutionNarrativeExportHistory(exports=serialized)


@router.get(
    "/exports/narrative/jobs",
    summary="Summarize narrative export packaging workload",
)
async def summarize_narrative_export_jobs(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return queue depth and lifecycle telemetry for narrative packaging jobs."""

    queue_snapshot = get_packaging_queue_snapshot()
    del user

    status_rows = (
        db.query(
            models.ExecutionNarrativeExport.artifact_status,
            func.count(models.ExecutionNarrativeExport.id),
        )
        .group_by(models.ExecutionNarrativeExport.artifact_status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}
    last_failure = (
        db.query(models.ExecutionNarrativeExport)
        .filter(models.ExecutionNarrativeExport.artifact_status == "failed")
        .order_by(models.ExecutionNarrativeExport.updated_at.desc())
        .first()
    )
    last_failure_at = (
        last_failure.updated_at.isoformat() if last_failure else None
    )
    return {
        "queue": queue_snapshot,
        "status_counts": status_counts,
        "last_failure_at": last_failure_at,
    }


@router.post(
    "/sessions/{execution_id}/exports/narrative/{export_id}/approve",
    response_model=schemas.ExecutionNarrativeExport,
)
async def approve_execution_narrative_export(
    execution_id: str,
    export_id: str,
    approval: schemas.ExecutionNarrativeApprovalRequest,
    dry_run: bool = Query(
        default=False,
        description="Re-evaluate guardrails without dispatching packaging",
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Record approval or rejection metadata for a narrative export."""

    # purpose: attach compliance signature data to persisted narrative exports
    # inputs: execution and export identifiers with approval payload
    # outputs: updated ExecutionNarrativeExport reflecting approval state
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        export_uuid = UUID(export_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier supplied") from exc

    export_record = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            ),
            joinedload(models.ExecutionNarrativeExport.execution),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(
            models.ExecutionNarrativeExport.id == export_uuid,
            models.ExecutionNarrativeExport.execution_id == exec_uuid,
        )
        .first()
    )
    if not export_record:
        raise HTTPException(status_code=404, detail="Narrative export not found")

    result = approval_ladders.record_stage_decision(
        db,
        export=export_record,
        approval=approval,
        acting_user=user,
    )
    should_queue_packaging = result.should_queue_packaging

    db.commit()
    db.refresh(export_record)

    if should_queue_packaging:
        queued_packaging = approval_ladders.dispatch_export_for_packaging(
            db,
            export=export_record,
            actor=user,
            enqueue=enqueue_narrative_export_packaging,
            dry_run=dry_run,
        )
        db.commit()
        if queued_packaging:
            db.refresh(export_record)

    payload = _build_export_payload(db, export_record)
    if payload.artifact_status == "ready" and payload.artifact_file:
        payload.artifact_download_path = _build_artifact_download_path(
            payload.execution_id, payload.id
        )
        try:
            payload.artifact_signed_url = generate_signed_download_url(
                payload.artifact_file.storage_path
            )
        except FileNotFoundError:
            payload.artifact_signed_url = None
    else:
        payload.artifact_download_path = None
        payload.artifact_signed_url = None

    return payload


@router.post(
    "/sessions/{execution_id}/exports/narrative/{export_id}/stages/{stage_id}/delegate",
    response_model=schemas.ExecutionNarrativeExport,
)
async def delegate_execution_narrative_approval_stage(
    execution_id: str,
    export_id: str,
    stage_id: str,
    request: schemas.ExecutionNarrativeApprovalDelegationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Assign or update the delegate for an approval stage."""

    # purpose: support stage delegation management from experiment console
    # inputs: execution/export identifiers, stage identifier, delegation payload
    # outputs: refreshed export payload reflecting delegation updates
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        export_uuid = UUID(export_id)
        stage_uuid = UUID(stage_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier supplied") from exc

    export_record = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            ),
            joinedload(models.ExecutionNarrativeExport.execution),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(
            models.ExecutionNarrativeExport.id == export_uuid,
            models.ExecutionNarrativeExport.execution_id == exec_uuid,
        )
        .first()
    )
    if not export_record:
        raise HTTPException(status_code=404, detail="Narrative export not found")

    export_record = approval_ladders.delegate_stage(
        db,
        export=export_record,
        stage_id=stage_uuid,
        payload=request,
        acting_user=user,
    )

    db.commit()
    db.refresh(export_record)

    return _build_export_payload(db, export_record)


@router.post(
    "/sessions/{execution_id}/exports/narrative/{export_id}/stages/{stage_id}/reset",
    response_model=schemas.ExecutionNarrativeExport,
)
async def reset_execution_narrative_approval_stage(
    execution_id: str,
    export_id: str,
    stage_id: str,
    request: schemas.ExecutionNarrativeApprovalResetRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return an approval stage to a pending state for remediation."""

    # purpose: enable remediation loops by resetting a stage to pending
    # inputs: execution/export identifiers, stage identifier, reset payload
    # outputs: refreshed export payload reflecting reset status
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        export_uuid = UUID(export_id)
        stage_uuid = UUID(stage_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier supplied") from exc

    export_record = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            ),
            joinedload(models.ExecutionNarrativeExport.execution),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(
            models.ExecutionNarrativeExport.id == export_uuid,
            models.ExecutionNarrativeExport.execution_id == exec_uuid,
        )
        .first()
    )
    if not export_record:
        raise HTTPException(status_code=404, detail="Narrative export not found")

    export_record = approval_ladders.reset_stage(
        db,
        export=export_record,
        stage_id=stage_uuid,
        payload=request,
        acting_user=user,
    )

    db.commit()
    db.refresh(export_record)

    return _build_export_payload(db, export_record)


@router.get(
    "/sessions/{execution_id}/exports/narrative/{export_id}/artifact",
)
async def download_execution_narrative_export_artifact(
    execution_id: str,
    export_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Stream the packaged dossier for a narrative export."""

    # purpose: deliver durable export packages for console downloads
    # inputs: execution identifier, export identifier, authenticated user
    # outputs: zipped dossier containing Markdown and bundled evidence
    # status: pilot
    try:
        exec_uuid = UUID(execution_id)
        export_uuid = UUID(export_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid identifier supplied") from exc

    export_record = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.execution),
        )
        .filter(
            models.ExecutionNarrativeExport.id == export_uuid,
            models.ExecutionNarrativeExport.execution_id == exec_uuid,
        )
        .first()
    )
    if not export_record:
        raise HTTPException(status_code=404, detail="Narrative export not found")

    now = datetime.now(timezone.utc)
    expires_at = export_record.retention_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at and expires_at < now:
        export_record.artifact_status = "expired"
        export_record.retired_at = now
        record_execution_event(
            db,
            export_record.execution,
            "narrative_export.packaging.expired",
            {
                "export_id": str(export_record.id),
                "version": export_record.version,
                "retention_expires_at": expires_at.isoformat(),
            },
            actor=user,
        )
        db.commit()
        raise HTTPException(status_code=410, detail="Narrative export artifact expired")

    if export_record.artifact_status != "ready" or not export_record.artifact_file:
        raise HTTPException(status_code=409, detail="Narrative export artifact not ready")

    try:
        data = load_binary_payload(export_record.artifact_file.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Artifact payload is unavailable") from exc

    checksum = hashlib.sha256(data).hexdigest()
    if export_record.artifact_checksum and checksum != export_record.artifact_checksum:
        export_record.artifact_status = "failed"
        export_record.artifact_error = "Checksum mismatch detected during download"
        record_execution_event(
            db,
            export_record.execution,
            "narrative_export.packaging.integrity_failed",
            {
                "export_id": str(export_record.id),
                "version": export_record.version,
                "expected_checksum": export_record.artifact_checksum,
                "observed_checksum": checksum,
            },
            actor=user,
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Artifact checksum validation failed")

    filename = (
        export_record.artifact_file.filename
        or f"execution-{execution_id}-narrative-v{export_record.version}.zip"
    )
    response = StreamingResponse(io.BytesIO(data), media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@router.post(
    "/sessions/{execution_id}/steps/{step_index}",
    response_model=schemas.ExperimentExecutionSessionOut,
)
async def update_step_status(
    execution_id: str,
    step_index: int,
    update: schemas.ExperimentStepStatusUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update status metadata for an individual experiment step."""

    # purpose: allow console to persist progress for specific instructions
    # inputs: execution identifier, step index, ExperimentStepStatusUpdate payload
    # outputs: ExperimentExecutionSessionOut reflecting updated progress
    # status: production
    if step_index < 0:
        raise HTTPException(status_code=400, detail="Step index must be non-negative")

    try:
        exec_uuid = UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid execution id") from exc

    execution = (
        db.query(models.ProtocolExecution)
        .filter(models.ProtocolExecution.id == exec_uuid)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    template = (
        db.query(models.ProtocolTemplate)
        .filter(models.ProtocolTemplate.id == execution.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Linked protocol template not found")

    params = execution.params or {}
    inventory_ids = _parse_uuid_list(params.get("inventory_item_ids", []))
    inventory_items = []
    if inventory_ids:
        inventory_items = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id.in_(inventory_ids))
            .all()
        )

    booking_ids = _parse_uuid_list(params.get("booking_ids", []))
    bookings = []
    if booking_ids:
        bookings = (
            db.query(models.Booking)
            .filter(models.Booking.id.in_(booking_ids))
            .all()
        )

    instructions = _extract_steps(template.content)
    if step_index >= len(instructions):
        raise HTTPException(status_code=404, detail="Step not found for template")

    gate_context = _prepare_step_gate_context(db, execution, inventory_items, bookings)
    step_states = _build_step_states(execution, instructions, gate_context)
    target_state = step_states[step_index]
    if (
        target_state.blocked_reason
        and target_state.status == "pending"
        and update.status in {"in_progress", "completed"}
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Step is blocked by orchestration rules",
                "blocked_reason": target_state.blocked_reason,
                "required_actions": target_state.required_actions,
                "auto_triggers": target_state.auto_triggers,
            },
        )

    _store_step_progress(execution, step_index, update)

    record_execution_event(
        db,
        execution,
        "step.transition",
        {
            "step_index": step_index,
            "instruction": instructions[step_index],
            "from_status": target_state.status,
            "to_status": update.status,
            "auto": False,
        },
        user,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return _assemble_session(db, execution)
