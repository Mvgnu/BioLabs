"""Pydantic schemas for robotic instrumentation services."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InstrumentCapabilityCreate(BaseModel):
    capability_key: str
    title: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    guardrail_requirements: list[dict[str, Any]] = Field(default_factory=list)


class InstrumentCapabilityOut(BaseModel):
    id: UUID
    equipment_id: UUID
    capability_key: str
    title: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    guardrail_requirements: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentSOPSummary(BaseModel):
    sop_id: UUID
    title: str
    version: int
    status: str
    effective_at: datetime
    retired_at: Optional[datetime] = None


class InstrumentSOPLinkCreate(BaseModel):
    sop_id: UUID
    status: str = "active"


class InstrumentReservationCreate(BaseModel):
    planner_session_id: Optional[UUID] = None
    protocol_execution_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    scheduled_start: datetime
    scheduled_end: datetime
    run_parameters: dict[str, Any] = Field(default_factory=dict)


class InstrumentReservationOut(BaseModel):
    id: UUID
    equipment_id: UUID
    planner_session_id: Optional[UUID]
    protocol_execution_id: Optional[UUID]
    team_id: Optional[UUID]
    requested_by_id: UUID
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    run_parameters: dict[str, Any]
    guardrail_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentRunDispatch(BaseModel):
    run_parameters: dict[str, Any] = Field(default_factory=dict)


class InstrumentRunStatusUpdate(BaseModel):
    status: str
    guardrail_flags: list[str] = Field(default_factory=list)


class InstrumentRunOut(BaseModel):
    id: UUID
    reservation_id: Optional[UUID]
    equipment_id: UUID
    team_id: Optional[UUID]
    planner_session_id: Optional[UUID]
    protocol_execution_id: Optional[UUID]
    status: str
    run_parameters: dict[str, Any]
    guardrail_flags: list[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentTelemetrySampleCreate(BaseModel):
    channel: str
    payload: dict[str, Any] = Field(default_factory=dict)


class InstrumentTelemetrySampleOut(BaseModel):
    id: UUID
    run_id: UUID
    channel: str
    payload: dict[str, Any]
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentProfile(BaseModel):
    equipment_id: UUID
    name: str
    eq_type: Optional[str]
    status: str
    team_id: Optional[UUID]
    capabilities: list[InstrumentCapabilityOut] = Field(default_factory=list)
    sops: list[InstrumentSOPSummary] = Field(default_factory=list)
    next_reservation: Optional[InstrumentReservationOut] = None
    active_run: Optional[InstrumentRunOut] = None
    custody_alerts: list[dict[str, Any]] = Field(default_factory=list)


class InstrumentRunTelemetryEnvelope(BaseModel):
    run: InstrumentRunOut
    samples: list[InstrumentTelemetrySampleOut] = Field(default_factory=list)


class InstrumentSimulationRequest(BaseModel):
    scenario: str = Field(default="thermal_cycle")
    team_id: Optional[UUID] = None
    planner_session_id: Optional[UUID] = None
    protocol_execution_id: Optional[UUID] = None
    run_parameters: dict[str, Any] = Field(default_factory=dict)
    duration_minutes: int = Field(default=30, ge=1, le=480)


class InstrumentSimulationEvent(BaseModel):
    sequence: int
    event_type: Literal["status", "telemetry"]
    recorded_at: datetime
    payload: dict[str, Any]


class InstrumentSimulationResult(BaseModel):
    reservation: InstrumentReservationOut
    run: InstrumentRunOut
    envelope: InstrumentRunTelemetryEnvelope
    events: list[InstrumentSimulationEvent] = Field(default_factory=list)
