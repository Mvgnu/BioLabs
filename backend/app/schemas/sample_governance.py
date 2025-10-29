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
    compartment_id: UUID | None = None
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
