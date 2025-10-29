"""Schemas for custody governance services."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FreezerCompartmentNode(BaseModel):
    id: UUID
    label: str
    position_index: int
    capacity: int | None = None
    guardrail_thresholds: dict[str, Any]
    occupancy: int
    guardrail_flags: list[str]
    latest_activity_at: datetime | None = None
    children: list["FreezerCompartmentNode"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FreezerUnitTopology(BaseModel):
    id: UUID
    name: str
    status: str
    facility_code: str | None = None
    guardrail_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    compartments: list[FreezerCompartmentNode] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SampleCustodyLogBase(BaseModel):
    asset_version_id: UUID | None = None
    planner_session_id: UUID | None = None
    protocol_execution_id: UUID | None = None
    execution_event_id: UUID | None = None
    compartment_id: UUID | None = None
    inventory_item_id: UUID | None = None
    custody_action: str = Field(min_length=1)
    quantity: int | None = None
    quantity_units: str | None = None
    performed_for_team_id: UUID | None = None
    performed_at: datetime | None = None
    notes: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class SampleCustodyLogCreate(SampleCustodyLogBase):
    pass


class SampleCustodyLogOut(SampleCustodyLogBase):
    id: UUID
    guardrail_flags: list[str]
    created_at: datetime
    performed_by_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class InventorySampleSummary(BaseModel):
    id: UUID
    name: str
    item_type: str
    team_id: UUID | None = None
    custody_state: str | None = None
    custody_snapshot: dict[str, Any] = Field(default_factory=dict)
    guardrail_flags: list[str] = Field(default_factory=list)
    linked_planner_session_ids: list[UUID] = Field(default_factory=list)
    linked_asset_version_ids: list[UUID] = Field(default_factory=list)
    open_escalations: int = 0
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SampleDetail(BaseModel):
    item: InventorySampleSummary
    recent_logs: list[SampleCustodyLogOut] = Field(default_factory=list)
    escalations: list[CustodyEscalation] = Field(default_factory=list)


class ProtocolExecutionContext(BaseModel):
    id: UUID
    status: str
    run_by: UUID | None = None
    template_id: UUID | None = None
    template_name: str | None = None
    guardrail_status: str | None = None
    guardrail_state: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustodyEscalation(BaseModel):
    id: UUID
    status: str
    severity: str
    reason: str
    due_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    assigned_to_id: UUID | None = None
    guardrail_flags: list[str]
    notifications: list[dict[str, Any]]
    meta: dict[str, Any]
    log_id: UUID | None = None
    freezer_unit_id: UUID | None = None
    compartment_id: UUID | None = None
    asset_version_id: UUID | None = None
    protocol_execution_id: UUID | None = None
    execution_event_id: UUID | None = None
    protocol_execution: ProtocolExecutionContext | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustodyEscalationAck(BaseModel):
    acknowledged_at: datetime
    status: str


class CustodyProtocolExecution(BaseModel):
    id: UUID
    status: str
    guardrail_status: str
    guardrail_state: dict[str, Any]
    template_id: UUID | None = None
    template_name: str | None = None
    template_team_id: UUID | None = None
    run_by: UUID | None = None
    open_escalations: int = 0
    open_drill_count: int = 0
    qc_backpressure: bool = False
    event_overlays: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FreezerFault(BaseModel):
    id: UUID
    freezer_unit_id: UUID
    compartment_id: UUID | None = None
    fault_type: str
    severity: str
    guardrail_flag: str | None = None
    occurred_at: datetime
    resolved_at: datetime | None = None
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FreezerFaultCreate(BaseModel):
    compartment_id: UUID | None = None
    fault_type: str
    severity: str = Field(min_length=1)
    guardrail_flag: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
