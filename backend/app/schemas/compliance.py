"""Pydantic schemas for compliance residency and legal hold APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    name: str
    slug: str
    primary_region: str
    residency_enforced: bool = True
    allowed_regions: list[str] = Field(default_factory=list)
    encryption_policy: dict[str, Any] = Field(default_factory=dict)
    retention_policy: dict[str, Any] = Field(default_factory=dict)


class OrganizationCreate(OrganizationBase):
    """Payload for creating an organization."""


class OrganizationUpdate(BaseModel):
    """Selective update payload for organization configuration."""

    name: str | None = None
    slug: str | None = None
    primary_region: str | None = None
    residency_enforced: bool | None = None
    allowed_regions: list[str] | None = None
    encryption_policy: dict[str, Any] | None = None
    retention_policy: dict[str, Any] | None = None


class OrganizationOut(OrganizationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    policy_count: int = 0
    active_legal_holds: int = 0

    model_config = ConfigDict(from_attributes=True)


class ResidencyPolicyPayload(BaseModel):
    data_domain: str
    allowed_regions: list[str]
    default_region: str
    encryption_at_rest: str
    encryption_in_transit: str
    retention_days: int = 365
    audit_interval_days: int = 30
    guardrail_flags: list[str] = Field(default_factory=list)


class ResidencyPolicyOut(ResidencyPolicyPayload):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalHoldCreate(BaseModel):
    scope_type: str
    scope_reference: str
    reason: str


class LegalHoldOut(BaseModel):
    id: UUID
    scope_type: str
    scope_reference: str
    reason: str
    status: str
    created_at: datetime
    released_at: datetime | None = None
    release_notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ResidencyEvaluation(BaseModel):
    allowed: bool
    effective_region: str | None
    flags: list[str] = Field(default_factory=list)


class ComplianceOrganizationReport(BaseModel):
    id: UUID
    name: str
    primary_region: str
    residency_enforced: bool
    policy_count: int
    active_holds: int
    residency_gaps: list[str] = Field(default_factory=list)
    record_status_totals: dict[str, int] = Field(default_factory=dict)


class ComplianceReport(BaseModel):
    generated_at: datetime
    organizations: list[ComplianceOrganizationReport]


class ComplianceRecordPayload(BaseModel):
    item_id: UUID | None = None
    organization_id: UUID | None = None
    record_type: str
    data_domain: str = "general"
    status: str = "pending"
    notes: str | None = None
    region: str | None = None


class ComplianceRecordUpdatePayload(BaseModel):
    status: str | None = None
    notes: str | None = None
    region: str | None = None


class ComplianceRecordOut(BaseModel):
    id: UUID
    item_id: UUID | None
    user_id: UUID | None
    organization_id: UUID | None
    record_type: str
    data_domain: str
    status: str
    notes: str | None
    region: str | None
    guardrail_flags: list[str] = Field(default_factory=list)
    retention_period_days: int | None = None
    encryption_profile: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceSummaryRow(BaseModel):
    status: str
    count: int

