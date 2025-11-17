from datetime import datetime
from typing import Any, Literal, Optional
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
    federation_links: list["DNARepositoryFederationLinkOut"] = []
    release_channels: list["DNARepositoryReleaseChannelOut"] = []
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
    lifecycle_snapshot: dict = Field(
        default_factory=dict,
        description="Captured lifecycle aggregation context for provenance",
    )
    mitigation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Historical guardrail mitigation actions applied to the release",
    )
    replay_checkpoint: dict = Field(
        default_factory=dict,
        description="Planner replay checkpoint payload aligning release assets",
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
    planner_session_id: Optional[UUID]
    lifecycle_snapshot: dict
    mitigation_history: list[dict[str, Any]]
    replay_checkpoint: dict
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


class DNARepositoryFederationLinkCreate(BaseModel):
    external_repository_id: str
    external_organization: str
    permissions: dict = Field(default_factory=dict)
    guardrail_contract: dict = Field(default_factory=dict)


class DNARepositoryFederationLinkOut(BaseModel):
    id: UUID
    repository_id: UUID
    external_repository_id: str
    external_organization: str
    trust_state: str
    permissions: dict
    guardrail_contract: dict
    last_attested_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    attestations: list["DNARepositoryFederationAttestationOut"] = []
    grants: list["DNARepositoryFederationGrantOut"] = []
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryFederationAttestationCreate(BaseModel):
    release_id: Optional[UUID] = None
    attestor_organization: str
    attestor_contact: Optional[str] = None
    guardrail_summary: dict = Field(default_factory=dict)
    provenance_notes: Optional[str] = None


class DNARepositoryFederationAttestationOut(BaseModel):
    id: UUID
    link_id: UUID
    release_id: Optional[UUID]
    attestor_organization: str
    attestor_contact: Optional[str]
    guardrail_summary: dict
    provenance_notes: Optional[str]
    created_at: datetime
    created_by_id: Optional[UUID]
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryFederationGrantCreate(BaseModel):
    organization: str
    permission_tier: Literal["reviewer", "publisher", "observer"] = "reviewer"
    guardrail_scope: dict = Field(default_factory=dict)


class DNARepositoryFederationGrantDecision(BaseModel):
    decision: Literal["approve", "revoke"]
    notes: Optional[str] = None


class DNARepositoryFederationGrantOut(BaseModel):
    id: UUID
    link_id: UUID
    organization: str
    permission_tier: str
    guardrail_scope: dict
    handshake_state: str
    requested_by_id: Optional[UUID]
    approved_by_id: Optional[UUID]
    activated_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryReleaseChannelCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    audience_scope: Literal["internal", "partners", "public"] = "internal"
    guardrail_profile: dict = Field(default_factory=dict)
    federation_link_id: Optional[UUID] = None


class DNARepositoryReleaseChannelOut(BaseModel):
    id: UUID
    repository_id: UUID
    federation_link_id: Optional[UUID]
    name: str
    slug: str
    description: Optional[str]
    audience_scope: str
    guardrail_profile: dict
    created_at: datetime
    updated_at: datetime
    versions: list["DNARepositoryReleaseChannelVersionOut"] = []
    model_config = ConfigDict(from_attributes=True)


class DNARepositoryReleaseChannelVersionCreate(BaseModel):
    release_id: UUID
    version_label: str
    guardrail_attestation: dict = Field(default_factory=dict)
    provenance_snapshot: dict = Field(default_factory=dict)
    mitigation_digest: Optional[str] = None
    grant_id: Optional[UUID] = None


class DNARepositoryReleaseChannelVersionOut(BaseModel):
    id: UUID
    channel_id: UUID
    release_id: UUID
    sequence: int
    version_label: str
    guardrail_attestation: dict
    provenance_snapshot: dict
    mitigation_digest: Optional[str]
    created_at: datetime
    grant_id: Optional[UUID]
    model_config = ConfigDict(from_attributes=True)

