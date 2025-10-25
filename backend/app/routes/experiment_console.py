from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
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

    db.add(execution)
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
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return _assemble_session(db, execution)

