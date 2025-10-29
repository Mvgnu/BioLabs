from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DNARepositoryGuardrailPolicy(BaseModel):
    name: str = Field(..., description="Human-friendly policy label")
    approval_threshold: int = Field(1, ge=1, le=10)
    requires_custody_clearance: bool = Field(True)
    requires_planner_link: bool = Field(True)
    mitigation_playbooks: list[str] = Field(default_factory=list)


class DNARepositoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    guardrail_policy: DNARepositoryGuardrailPolicy


class DNARepositoryCreate(DNARepositoryBase):
    team_id: Optional[UUID] = None


class DNARepositoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    guardrail_policy: Optional[DNARepositoryGuardrailPolicy] = None
    team_id: Optional[UUID] = None


class DNARepositoryOut(DNARepositoryBase):
    id: UUID
    owner_id: UUID
    team_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    collaborators: list["DNARepositoryCollaboratorOut"] = []
    releases: list["DNARepositoryReleaseOut"] = []
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryCollaboratorAdd(BaseModel):
    user_id: UUID
    role: Literal["viewer", "contributor", "maintainer", "owner"] = "contributor"


class DNARepositoryCollaboratorOut(BaseModel):
    id: UUID
    repository_id: UUID
    user_id: UUID
    role: str
    invitation_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryReleaseCreate(BaseModel):
    version: str
    title: str
    notes: Optional[str] = None
    guardrail_snapshot: dict = Field(default_factory=dict)
    mitigation_summary: Optional[str] = None
    planner_session_id: Optional[UUID] = Field(
        default=None,
        description="Optional planner session anchor enforcing custody checks",
    )


class DNARepositoryReleaseOut(BaseModel):
    id: UUID
    repository_id: UUID
    version: str
    title: str
    notes: Optional[str]
    status: str
    guardrail_state: str
    guardrail_snapshot: dict
    mitigation_summary: Optional[str]
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    approvals: list["DNARepositoryReleaseApprovalOut"] = []
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryReleaseApprovalCreate(BaseModel):
    notes: Optional[str] = None
    guardrail_flags: list[str] = Field(default_factory=list)
    status: Literal["approved", "rejected"]


class DNARepositoryReleaseApprovalOut(BaseModel):
    id: UUID
    release_id: UUID
    approver_id: UUID
    status: str
    guardrail_flags: list[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryTimelineEventOut(BaseModel):
    id: UUID
    repository_id: UUID
    release_id: Optional[UUID]
    event_type: str
    payload: dict
    created_at: datetime
    created_by_id: Optional[UUID]
    model_config = ConfigDict(from_attributes=True)

