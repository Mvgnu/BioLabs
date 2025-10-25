from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/experiment-console", tags=["experiment-console"])


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
) -> list[schemas.ExperimentStepStatus]:
    """Combine instructions with persisted execution progress."""

    # purpose: align persisted step status metadata with derived instructions
    # inputs: execution record, list of instruction strings
    # outputs: ExperimentStepStatus objects representing current progress
    # status: production
    result_payload = execution.result or {}
    stored_steps = result_payload.get("steps", {}) if isinstance(result_payload, dict) else {}
    step_statuses: list[schemas.ExperimentStepStatus] = []

    for index, instruction in enumerate(instructions):
        stored = stored_steps.get(str(index), {}) if isinstance(stored_steps, dict) else {}
        step_statuses.append(
            schemas.ExperimentStepStatus(
                index=index,
                instruction=instruction,
                status=stored.get("status", "pending"),
                started_at=_coerce_datetime(stored.get("started_at")),
                completed_at=_coerce_datetime(stored.get("completed_at")),
            )
        )
    return step_statuses


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
    steps = _build_step_states(execution, instructions)

    return schemas.ExperimentExecutionSessionOut(
        execution=execution,
        protocol=template,
        notebook_entries=notebook_entries,
        inventory_items=inventory_items,
        bookings=bookings,
        steps=steps,
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

    instructions = _extract_steps(template.content)
    if step_index >= len(instructions):
        raise HTTPException(status_code=404, detail="Step not found for template")

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
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return _assemble_session(db, execution)

