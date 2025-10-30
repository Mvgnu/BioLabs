"""Robotic instrumentation orchestration services."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas

# purpose: orchestrate robotic instrument reservations, runs, and telemetry with custody guardrails
# status: pilot
# depends_on: backend.app.models.Equipment, backend.app.models.InstrumentRunReservation
# related_docs: docs/instrumentation/README.md

_ACTIVE_RESERVATION_STATUSES = {"scheduled", "pending_clearance", "in_progress"}
_ACTIVE_RUN_STATUSES = {"queued", "running"}
_GUARDRAIL_BLOCKING_SEVERITY = {"critical"}

_SIMULATION_SCENARIOS: dict[str, list[dict[str, object]]] = {
    "thermal_cycle": [
        {"event_type": "telemetry", "channel": "temperature", "payload": {"value": 25.0}, "offset_seconds": 0},
        {"event_type": "telemetry", "channel": "temperature", "payload": {"value": 72.5}, "offset_seconds": 120},
        {"event_type": "telemetry", "channel": "temperature", "payload": {"value": 94.0}, "offset_seconds": 240},
        {"event_type": "telemetry", "channel": "amplification", "payload": {"cycle": 25, "signal": 0.82}, "offset_seconds": 360},
        {"event_type": "status", "status": "completed", "guardrail_flags": [], "offset_seconds": 420},
    ],
    "incubation_qc": [
        {"event_type": "telemetry", "channel": "incubation", "payload": {"humidity": 40.2}, "offset_seconds": 0},
        {"event_type": "telemetry", "channel": "incubation", "payload": {"humidity": 44.1}, "offset_seconds": 180},
        {"event_type": "telemetry", "channel": "incubation", "payload": {"humidity": 43.8}, "offset_seconds": 360},
        {"event_type": "telemetry", "channel": "alert", "payload": {"code": "qc.window", "level": "info"}, "offset_seconds": 420},
        {"event_type": "status", "status": "completed", "guardrail_flags": ["qc.window"], "offset_seconds": 540},
    ],
}


class InstrumentationError(RuntimeError):
    """Base error for instrumentation orchestration."""


class ReservationConflict(InstrumentationError):
    """Raised when a reservation overlaps an existing booking."""


class GuardrailViolation(InstrumentationError):
    """Raised when guardrail checks block dispatch."""


class InstrumentNotFound(InstrumentationError):
    """Raised when an instrument or run cannot be located."""


class CapabilityConflict(InstrumentationError):
    """Raised when capability metadata conflicts with existing definitions."""


class SOPNotFound(InstrumentationError):
    """Raised when a requested SOP cannot be located."""


def list_instrument_profiles(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[schemas.InstrumentProfile]:
    """Return orchestration-ready instrument profiles."""

    equipment_query = (
        db.query(models.Equipment)
        .options(
            joinedload(models.Equipment.capabilities),
            joinedload(models.Equipment.sop_links).joinedload(models.InstrumentSOPLink.sop),
            joinedload(models.Equipment.reservations),
            joinedload(models.Equipment.runs),
        )
        .order_by(models.Equipment.name.asc())
    )
    if team_id:
        equipment_query = equipment_query.filter(
            sa.or_(
                models.Equipment.team_id.is_(None),
                models.Equipment.team_id == team_id,
            )
        )
    devices: list[models.Equipment] = equipment_query.all()
    if not devices:
        return []

    custody_alerts = _load_custody_alerts(db, team_id)
    profiles: list[schemas.InstrumentProfile] = []
    for device in devices:
        next_reservation = _select_next_reservation(device.reservations)
        active_run = _select_active_run(device.runs)
        sop_summaries = [
            schemas.InstrumentSOPSummary(
                sop_id=link.sop_id,
                title=link.sop.title,
                version=link.sop.version,
                status=link.status,
                effective_at=link.effective_at,
                retired_at=link.retired_at,
            )
            for link in device.sop_links
            if link.sop is not None
        ]
        profile = schemas.InstrumentProfile(
            equipment_id=device.id,
            name=device.name,
            eq_type=device.eq_type,
            status=device.status,
            team_id=device.team_id,
            capabilities=[schemas.InstrumentCapabilityOut.model_validate(cap) for cap in device.capabilities],
            sops=sop_summaries,
            next_reservation=schemas.InstrumentReservationOut.model_validate(next_reservation)
            if next_reservation
            else None,
            active_run=schemas.InstrumentRunOut.model_validate(active_run)
            if active_run
            else None,
            custody_alerts=custody_alerts.get(device.team_id, []),
        )
        profiles.append(profile)
    return profiles


def register_capability(
    db: Session,
    equipment_id: UUID,
    payload: schemas.InstrumentCapabilityCreate,
) -> models.InstrumentCapability:
    """Attach a capability descriptor to an instrument."""

    equipment = db.get(models.Equipment, equipment_id)
    if not equipment:
        raise InstrumentNotFound(f"equipment {equipment_id} not found")

    existing = (
        db.query(models.InstrumentCapability)
        .filter(
            models.InstrumentCapability.equipment_id == equipment_id,
            models.InstrumentCapability.capability_key == payload.capability_key,
        )
        .first()
    )
    if existing:
        raise CapabilityConflict("capability already registered for instrument")

    now = datetime.now(timezone.utc)
    capability = models.InstrumentCapability(
        equipment_id=equipment_id,
        capability_key=payload.capability_key,
        title=payload.title,
        parameters=payload.parameters,
        guardrail_requirements=payload.guardrail_requirements,
        created_at=now,
        updated_at=now,
    )
    db.add(capability)
    db.flush()
    db.refresh(capability)
    return capability


def link_sop(
    db: Session,
    equipment_id: UUID,
    payload: schemas.InstrumentSOPLinkCreate,
) -> models.InstrumentSOPLink:
    """Link an SOP to an instrument with lifecycle status."""

    equipment = db.get(models.Equipment, equipment_id)
    if not equipment:
        raise InstrumentNotFound(f"equipment {equipment_id} not found")
    sop = db.get(models.SOP, payload.sop_id)
    if not sop:
        raise SOPNotFound(f"sop {payload.sop_id} not found")

    existing = (
        db.query(models.InstrumentSOPLink)
        .filter(
            models.InstrumentSOPLink.equipment_id == equipment_id,
            models.InstrumentSOPLink.sop_id == payload.sop_id,
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.status = payload.status
        if payload.status == "retired":
            existing.retired_at = existing.retired_at or now
        else:
            existing.retired_at = None
        db.flush()
        db.refresh(existing)
        return existing

    link = models.InstrumentSOPLink(
        equipment_id=equipment_id,
        sop_id=payload.sop_id,
        status=payload.status,
        effective_at=now,
        retired_at=now if payload.status == "retired" else None,
    )
    db.add(link)
    db.flush()
    db.refresh(link)
    return link


def schedule_reservation(
    db: Session,
    equipment_id: UUID,
    payload: schemas.InstrumentReservationCreate,
    *,
    actor_id: UUID,
) -> models.InstrumentRunReservation:
    """Create an instrument reservation and attach guardrail context."""

    equipment = db.get(models.Equipment, equipment_id)
    if not equipment:
        raise InstrumentNotFound(f"equipment {equipment_id} not found")

    _assert_no_conflicts(db, equipment_id, payload.scheduled_start, payload.scheduled_end)

    guardrail_snapshot = _compile_guardrail_snapshot(
        db,
        team_id=payload.team_id or equipment.team_id,
        planner_session_id=payload.planner_session_id,
        protocol_execution_id=payload.protocol_execution_id,
    )
    status = "scheduled"
    if guardrail_snapshot["open_escalations"]:
        severities = {item["severity"] for item in guardrail_snapshot["open_escalations"]}
        status = "guardrail_blocked" if severities & _GUARDRAIL_BLOCKING_SEVERITY else "pending_clearance"

    reservation = models.InstrumentRunReservation(
        equipment_id=equipment_id,
        planner_session_id=payload.planner_session_id,
        protocol_execution_id=payload.protocol_execution_id,
        team_id=payload.team_id or equipment.team_id,
        requested_by_id=actor_id,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        status=status,
        run_parameters=payload.run_parameters,
        guardrail_snapshot=guardrail_snapshot,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(reservation)
    db.flush()
    db.refresh(reservation)
    return reservation


def dispatch_run(
    db: Session,
    reservation_id: UUID,
    payload: schemas.InstrumentRunDispatch,
) -> models.InstrumentRun:
    """Spawn a run from a reservation after evaluating guardrails."""

    reservation = db.get(models.InstrumentRunReservation, reservation_id)
    if not reservation:
        raise InstrumentNotFound(f"reservation {reservation_id} not found")
    if reservation.status == "guardrail_blocked":
        raise GuardrailViolation("reservation blocked by guardrail requirements")

    existing_active_run = (
        db.query(models.InstrumentRun)
        .filter(models.InstrumentRun.reservation_id == reservation_id)
        .filter(models.InstrumentRun.status.in_(_ACTIVE_RUN_STATUSES))
        .first()
    )
    if existing_active_run:
        raise ReservationConflict("reservation already has an active run")

    now = datetime.now(timezone.utc)
    reservation.status = "in_progress"
    reservation.updated_at = now
    merged_parameters = {**reservation.run_parameters, **(payload.run_parameters or {})}
    guardrail_flags = [
        f"custody:{entry['severity']}:{entry['reason']}"
        for entry in reservation.guardrail_snapshot.get("open_escalations", [])
    ]
    run = models.InstrumentRun(
        reservation_id=reservation.id,
        equipment_id=reservation.equipment_id,
        team_id=reservation.team_id,
        planner_session_id=reservation.planner_session_id,
        protocol_execution_id=reservation.protocol_execution_id,
        status="running",
        run_parameters=merged_parameters,
        guardrail_flags=guardrail_flags,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


def update_run_status(
    db: Session,
    run_id: UUID,
    payload: schemas.InstrumentRunStatusUpdate,
) -> models.InstrumentRun:
    """Update run lifecycle state with guardrail annotations."""

    run = db.get(models.InstrumentRun, run_id)
    if not run:
        raise InstrumentNotFound(f"run {run_id} not found")

    now = datetime.now(timezone.utc)
    run.status = payload.status
    run.guardrail_flags = payload.guardrail_flags
    run.updated_at = now
    if payload.status in {"completed", "failed", "cancelled"}:
        run.completed_at = now
        if run.reservation:
            run.reservation.status = payload.status
            run.reservation.updated_at = now
    db.flush()
    db.refresh(run)
    return run


def record_telemetry_sample(
    db: Session,
    run_id: UUID,
    payload: schemas.InstrumentTelemetrySampleCreate,
) -> models.InstrumentTelemetrySample:
    """Persist telemetry envelope for a running instrument."""

    run = db.get(models.InstrumentRun, run_id)
    if not run:
        raise InstrumentNotFound(f"run {run_id} not found")
    if run.status not in _ACTIVE_RUN_STATUSES:
        raise GuardrailViolation("cannot stream telemetry for inactive run")

    sample = models.InstrumentTelemetrySample(
        run_id=run_id,
        channel=payload.channel,
        payload=payload.payload,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(sample)
    db.flush()
    db.refresh(sample)
    return sample


def list_runs(
    db: Session,
    *,
    equipment_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[models.InstrumentRun]:
    """Return instrument runs filtered by scope."""

    run_query = db.query(models.InstrumentRun).order_by(models.InstrumentRun.created_at.desc())
    if equipment_id:
        run_query = run_query.filter(models.InstrumentRun.equipment_id == equipment_id)
    if status:
        run_query = run_query.filter(models.InstrumentRun.status == status)
    return run_query.limit(limit).all()


def load_run_envelope(db: Session, run_id: UUID) -> schemas.InstrumentRunTelemetryEnvelope:
    """Load run metadata with telemetry samples."""

    run = (
        db.query(models.InstrumentRun)
        .options(joinedload(models.InstrumentRun.telemetry_samples))
        .filter(models.InstrumentRun.id == run_id)
        .one_or_none()
    )
    if not run:
        raise InstrumentNotFound(f"run {run_id} not found")

    return schemas.InstrumentRunTelemetryEnvelope(
        run=schemas.InstrumentRunOut.model_validate(run),
        samples=[schemas.InstrumentTelemetrySampleOut.model_validate(s) for s in sorted(
            run.telemetry_samples, key=lambda sample: sample.recorded_at
        )],
    )


def simulate_run(
    db: Session,
    equipment_id: UUID,
    payload: schemas.InstrumentSimulationRequest,
    *,
    actor_id: UUID,
) -> schemas.InstrumentSimulationResult:
    """Create a deterministic simulation run and emit timeline events."""

    # purpose: deterministic simulation harness for digital twin dashboards and worker pipelines
    # status: experimental
    # inputs: Session db, UUID equipment_id, InstrumentSimulationRequest payload, UUID actor_id
    # outputs: InstrumentSimulationResult with reservation, run, telemetry timeline

    scenario = _SIMULATION_SCENARIOS.get(payload.scenario)
    if scenario is None:
        raise InstrumentationError(f"unknown simulation scenario '{payload.scenario}'")

    now = datetime.now(timezone.utc)
    reservation_payload = schemas.InstrumentReservationCreate(
        planner_session_id=payload.planner_session_id,
        protocol_execution_id=payload.protocol_execution_id,
        team_id=payload.team_id,
        scheduled_start=now,
        scheduled_end=now + timedelta(minutes=payload.duration_minutes),
        run_parameters=payload.run_parameters,
    )
    reservation = schedule_reservation(
        db,
        equipment_id,
        reservation_payload,
        actor_id=actor_id,
    )

    run = dispatch_run(
        db,
        reservation.id,
        schemas.InstrumentRunDispatch(run_parameters=payload.run_parameters),
    )

    sequence = 1
    base_time = now
    events: list[schemas.InstrumentSimulationEvent] = []

    for step in scenario:
        recorded_at = base_time + timedelta(seconds=int(step.get("offset_seconds", 0) or 0))
        recorded_at_naive = recorded_at.astimezone(timezone.utc).replace(tzinfo=None)
        event_type = step.get("event_type")
        if event_type == "telemetry":
            sample_payload = schemas.InstrumentTelemetrySampleCreate(
                channel=str(step.get("channel", "unknown")),
                payload={**(step.get("payload") or {}), "simulated": True},
            )
            sample = record_telemetry_sample(db, run.id, sample_payload)
            sample.recorded_at = recorded_at_naive
            db.flush()
            events.append(
                schemas.InstrumentSimulationEvent(
                    sequence=sequence,
                    event_type="telemetry",
                    recorded_at=sample.recorded_at,
                    payload={
                        "channel": sample.channel,
                        "payload": sample.payload,
                    },
                )
            )
        elif event_type == "status":
            status_value = str(step.get("status", "running"))
            guardrail_flags = [str(flag) for flag in step.get("guardrail_flags", [])]
            run = update_run_status(
                db,
                run.id,
                schemas.InstrumentRunStatusUpdate(
                    status=status_value,
                    guardrail_flags=guardrail_flags,
                ),
            )
            run.updated_at = recorded_at_naive
            if status_value in {"completed", "failed", "cancelled"}:
                run.completed_at = recorded_at_naive
                if run.reservation:
                    run.reservation.updated_at = recorded_at_naive
            db.flush()
            events.append(
                schemas.InstrumentSimulationEvent(
                    sequence=sequence,
                    event_type="status",
                    recorded_at=recorded_at,
                    payload={
                        "status": status_value,
                        "guardrail_flags": guardrail_flags,
                    },
                )
            )
        else:
            continue
        sequence += 1

    envelope = load_run_envelope(db, run.id)
    return schemas.InstrumentSimulationResult(
        reservation=schemas.InstrumentReservationOut.model_validate(reservation),
        run=envelope.run,
        envelope=envelope,
        events=events,
    )


def _select_next_reservation(
    reservations: Iterable[models.InstrumentRunReservation],
) -> models.InstrumentRunReservation | None:
    active = [
        reservation
        for reservation in reservations
        if reservation.status in _ACTIVE_RESERVATION_STATUSES
    ]
    if not active:
        return None
    return sorted(active, key=lambda reservation: reservation.scheduled_start)[0]


def _select_active_run(runs: Iterable[models.InstrumentRun]) -> models.InstrumentRun | None:
    active = [run for run in runs if run.status in _ACTIVE_RUN_STATUSES]
    if not active:
        return None
    return sorted(active, key=lambda run: run.started_at or run.created_at)[0]


def _assert_no_conflicts(
    db: Session,
    equipment_id: UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
) -> None:
    conflict_exists = (
        db.query(models.InstrumentRunReservation)
        .filter(models.InstrumentRunReservation.equipment_id == equipment_id)
        .filter(models.InstrumentRunReservation.status.in_(_ACTIVE_RESERVATION_STATUSES))
        .filter(
            sa.and_(
                models.InstrumentRunReservation.scheduled_start < scheduled_end,
                models.InstrumentRunReservation.scheduled_end > scheduled_start,
            )
        )
        .first()
    )
    if conflict_exists:
        raise ReservationConflict("instrument already reserved for the selected window")


def _compile_guardrail_snapshot(
    db: Session,
    *,
    team_id: UUID | None,
    planner_session_id: UUID | None,
    protocol_execution_id: UUID | None,
) -> dict[str, object]:
    if not team_id:
        return {
            "open_escalations": [],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "team_id": None,
            "planner_session_id": planner_session_id,
            "protocol_execution_id": protocol_execution_id,
        }

    escalation_query = (
        db.query(models.GovernanceCustodyEscalation, models.GovernanceSampleCustodyLog)
        .join(
            models.GovernanceSampleCustodyLog,
            models.GovernanceCustodyEscalation.log_id == models.GovernanceSampleCustodyLog.id,
            isouter=True,
        )
        .filter(models.GovernanceCustodyEscalation.status.in_({"open", "acknowledged"}))
    )
    escalation_query = escalation_query.filter(
        models.GovernanceSampleCustodyLog.performed_for_team_id == team_id
    )
    escalations = escalation_query.all()
    open_escalations = [
        {
            "id": str(escalation.id),
            "severity": escalation.severity,
            "status": escalation.status,
            "reason": escalation.reason,
            "due_at": escalation.due_at.isoformat() if escalation.due_at else None,
        }
        for escalation, _ in escalations
    ]
    return {
        "open_escalations": open_escalations,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "team_id": str(team_id),
        "planner_session_id": planner_session_id,
        "protocol_execution_id": protocol_execution_id,
    }


def _load_custody_alerts(
    db: Session,
    team_id: UUID | None,
) -> dict[UUID | None, list[dict[str, object]]]:
    alerts: dict[UUID | None, list[dict[str, object]]] = defaultdict(list)
    escalation_query = db.query(models.GovernanceCustodyEscalation, models.GovernanceSampleCustodyLog)
    escalation_query = escalation_query.join(
        models.GovernanceSampleCustodyLog,
        models.GovernanceCustodyEscalation.log_id == models.GovernanceSampleCustodyLog.id,
        isouter=True,
    )
    escalation_query = escalation_query.filter(
        models.GovernanceCustodyEscalation.status.in_({"open", "acknowledged"})
    )
    if team_id:
        escalation_query = escalation_query.filter(
            models.GovernanceSampleCustodyLog.performed_for_team_id == team_id
        )
    for escalation, log in escalation_query.all():
        alerts[log.performed_for_team_id if log else None].append(
            {
                "id": str(escalation.id),
                "severity": escalation.severity,
                "status": escalation.status,
                "reason": escalation.reason,
                "due_at": escalation.due_at.isoformat() if escalation.due_at else None,
            }
        )
    return alerts
