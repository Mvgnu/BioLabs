from datetime import datetime, time
from typing import Optional, Any, Dict, Literal, List
from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator
from uuid import UUID


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    orcid_id: Optional[str] = None


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    phone_number: Optional[str] = None
    orcid_id: Optional[str] = None
    is_admin: bool = False
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    orcid_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: Optional[str] = None


class TwoFactorEnableOut(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorVerifyIn(BaseModel):
    code: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: UUID
    name: str
    model_config = ConfigDict(from_attributes=True)


class TeamMemberAdd(BaseModel):
    user_id: Optional[UUID] = None
    email: Optional[EmailStr] = None
    role: str = "member"


class TeamMemberOut(BaseModel):
    user: UserOut
    role: str
    model_config = ConfigDict(from_attributes=True)


class LocationBase(BaseModel):
    name: str
    parent_id: Optional[UUID] = None
    team_id: Optional[UUID] = None


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[UUID] = None


class LocationOut(LocationBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InventoryItemCreate(BaseModel):
    item_type: str
    name: str
    barcode: Optional[str] = None
    team_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    location: Dict[str, Any] = {}
    status: Optional[str] = None
    custom_data: Dict[str, Any] = {}


class InventoryItemUpdate(BaseModel):
    item_type: Optional[str] = None
    name: Optional[str] = None
    barcode: Optional[str] = None
    team_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    location: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None


class InventoryItemOut(BaseModel):
    id: UUID
    item_type: str
    name: str
    barcode: Optional[str]
    team_id: Optional[UUID]
    owner_id: Optional[UUID]
    location_id: Optional[UUID]
    location: Dict[str, Any]
    status: str
    custom_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FieldDefinitionCreate(BaseModel):
    entity_type: str
    field_key: str
    field_label: str
    field_type: str
    is_required: bool = False
    options: Optional[list[Dict[str, Any]]] = None
    validation: Optional[Dict[str, Any]] = None


class FieldDefinitionOut(FieldDefinitionCreate):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class ItemRelationshipCreate(BaseModel):
    from_item: UUID
    to_item: UUID
    relationship_type: str
    meta: Dict[str, Any] = {}


class ItemRelationshipOut(ItemRelationshipCreate):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class FileUpload(BaseModel):
    filename: str
    file_type: str
    file_size: int
    item_id: UUID | None = None
    meta: Dict[str, Any] = {}


class FileOut(FileUpload):
    id: UUID
    storage_path: str
    uploaded_by: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ItemGraphOut(BaseModel):
    nodes: list[InventoryItemOut]
    edges: list[ItemRelationshipOut]


class FacetCount(BaseModel):
    key: str
    count: int


class InventoryFacets(BaseModel):
    item_types: list[FacetCount]
    statuses: list[FacetCount]
    teams: list[FacetCount]
    fields: list[FieldDefinitionOut]


class BulkUpdateItem(BaseModel):
    id: UUID
    data: InventoryItemUpdate


class BulkUpdateRequest(BaseModel):
    items: list[BulkUpdateItem]


class BulkDeleteRequest(BaseModel):
    item_ids: list[UUID]


class BulkOperationResult(BaseModel):
    success: bool
    item_id: UUID
    error: Optional[str] = None


class BulkOperationResponse(BaseModel):
    results: list[BulkOperationResult]
    total: int
    successful: int
    failed: int


class ProtocolTemplateCreate(BaseModel):
    name: str
    content: str
    variables: list[str] = []
    is_public: bool = False
    forked_from: Optional[UUID] = None
    team_id: Optional[UUID] = None


class ProtocolTemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[list[str]] = None
    is_public: Optional[bool] = None
    forked_from: Optional[UUID] = None
    team_id: Optional[UUID] = None


class ProtocolTemplateOut(ProtocolTemplateCreate):
    id: UUID
    version: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProtocolExecutionCreate(BaseModel):
    template_id: UUID
    params: Dict[str, Any] = {}


class ProtocolExecutionUpdate(BaseModel):
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class ProtocolExecutionOut(BaseModel):
    id: UUID
    template_id: UUID
    run_by: Optional[UUID] = None
    status: str
    params: Dict[str, Any]
    result: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProtocolMergeRequestCreate(BaseModel):
    template_id: UUID
    content: str
    variables: list[str] = []


class ProtocolMergeRequestUpdate(BaseModel):
    status: Optional[str] = None


class ProtocolMergeRequestOut(BaseModel):
    id: UUID
    template_id: UUID
    proposer_id: Optional[UUID] = None
    content: str
    variables: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TroubleshootingArticleCreate(BaseModel):
    title: str
    category: str
    content: str


class TroubleshootingArticleUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None


class TroubleshootingArticleOut(BaseModel):
    id: UUID
    title: str
    category: str
    content: str
    created_by: Optional[UUID] = None
    success_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotebookEntryCreate(BaseModel):
    title: str
    content: str
    item_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    items: list[UUID] = []
    protocols: list[UUID] = []
    images: list[UUID] = []
    blocks: list[dict] = []


class NotebookEntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    item_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    items: Optional[list[UUID]] = None
    protocols: Optional[list[UUID]] = None
    images: Optional[list[UUID]] = None
    blocks: Optional[list[dict]] = None


class NotebookEntryOut(BaseModel):
    id: UUID
    title: str
    content: str
    item_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    items: list[UUID] = []
    protocols: list[UUID] = []
    images: list[UUID] = []
    blocks: list[dict] = []
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    is_locked: bool
    signed_by: Optional[UUID] = None
    signed_at: Optional[datetime] = None
    witness_id: Optional[UUID] = None
    witnessed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class NotebookEntryVersionOut(BaseModel):
    id: UUID
    entry_id: UUID
    title: str
    content: str
    blocks: list[dict] = []
    created_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CommentBase(BaseModel):
    content: str
    item_id: Optional[UUID] = None
    entry_id: Optional[UUID] = None
    knowledge_article_id: Optional[UUID] = None


class CommentCreate(CommentBase):
    pass


class CommentUpdate(BaseModel):
    content: Optional[str] = None


class CommentOut(CommentBase):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResourceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    team_id: Optional[UUID] = None


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_id: Optional[UUID] = None


class ResourceOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    team_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    resource_id: UUID
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


class BookingUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = None


class BookingOut(BaseModel):
    id: UUID
    resource_id: UUID
    user_id: UUID
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExperimentStepStatus(BaseModel):
    index: int
    instruction: str
    status: Literal["pending", "in_progress", "completed", "skipped"] = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    required_actions: list[str] = Field(default_factory=list)
    auto_triggers: list[str] = Field(default_factory=list)


class ExperimentExecutionSessionCreate(BaseModel):
    template_id: UUID
    title: Optional[str] = None
    inventory_item_ids: list[UUID] = Field(default_factory=list)
    booking_ids: list[UUID] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    auto_create_notebook: bool = True


class ExperimentStepStatusUpdate(BaseModel):
    status: Literal["pending", "in_progress", "completed", "skipped"]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EquipmentTelemetryChannel(BaseModel):
    """Summarized live channel information for an instrument feed."""

    equipment: "EquipmentOut"
    status: str | None = None
    stream_topics: list[str] = Field(default_factory=list)
    latest_reading: Optional["EquipmentReadingOut"] = None


class ExperimentAnomalySignal(BaseModel):
    """Auto-detected deviation captured from incoming telemetry."""

    equipment_id: UUID
    channel: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"
    timestamp: datetime


class ExperimentAutoLogEntry(BaseModel):
    """Notebook-ready log derived from telemetry or rule triggers."""

    source: str
    title: str
    body: str | None = None
    created_at: datetime


class ExecutionEventOut(BaseModel):
    """Serialized execution timeline event for console replay."""

    id: UUID
    execution_id: UUID
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor_id: UUID | None = None
    actor: Optional["UserOut"] = None
    sequence: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentTimelinePage(BaseModel):
    """Paginated view of execution events for timeline consumption."""

    events: list[ExecutionEventOut] = Field(default_factory=list)
    next_cursor: str | None = None


class ExecutionNarrativeAttachmentIn(BaseModel):
    """Attachment descriptor for narrative export evidence."""

    # purpose: capture user-selected evidence references for bundling
    # inputs: export creation request payload
    # outputs: normalized reference metadata for persistence
    # status: enhanced
    type: Literal[
        "timeline_event",
        "file",
        "notebook_entry",
        "analytics_snapshot",
        "qc_metric",
        "remediation_report",
    ] | None = Field(default=None, serialization_alias="kind")
    reference_id: UUID | None = None
    event_id: UUID | None = None
    file_id: UUID | None = None
    notebook_entry_id: UUID | None = None
    analytics_event_id: UUID | None = None
    qc_event_id: UUID | None = None
    remediation_event_id: UUID | None = None
    label: str | None = None
    context: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference(self) -> "ExecutionNarrativeAttachmentIn":
        identifiers = {
            "timeline_event": self.event_id,
            "file": self.file_id,
            "notebook_entry": self.notebook_entry_id,
            "analytics_snapshot": self.analytics_event_id,
            "qc_metric": self.qc_event_id,
            "remediation_report": self.remediation_event_id,
        }
        if self.reference_id is not None and self.type:
            identifiers[self.type] = self.reference_id

        provided = {k: v for k, v in identifiers.items() if v is not None}
        if not provided:
            raise ValueError("At least one reference identifier must be provided for attachments")
        if len(provided) > 1:
            raise ValueError("Provide exactly one reference identifier for each attachment")

        resolved_type, resolved_id = next(iter(provided.items()))
        if self.type is None:
            self.type = resolved_type
        elif self.type != resolved_type:
            raise ValueError("Attachment type does not match provided reference identifier")

        self.reference_id = resolved_id
        return self


class ExecutionNarrativeExportAttachmentOut(BaseModel):
    """Serialized export attachment providing evidence context."""

    id: UUID
    evidence_type: Literal[
        "timeline_event",
        "file",
        "notebook_entry",
        "analytics_snapshot",
        "qc_metric",
        "remediation_report",
    ]
    reference_id: UUID
    label: str | None = None
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="hydration_context",
        serialization_alias="hydration_context",
    )
    file: Optional[FileOut] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NarrativeEvidenceDescriptor(BaseModel):
    """Lightweight descriptor surfaced for evidence selection UIs."""

    # purpose: provide paginated selection metadata for narrative evidence domains
    # inputs: evidence discovery endpoints
    # outputs: context required to assemble narrative attachments
    # status: enhanced
    id: UUID
    type: Literal[
        "notebook_entry",
        "analytics_snapshot",
        "qc_metric",
        "remediation_report",
    ]
    label: str
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class NarrativeEvidencePage(BaseModel):
    """Paginated response for evidence discovery endpoints."""

    items: list[NarrativeEvidenceDescriptor] = Field(default_factory=list)
    next_cursor: str | None = None


class ExecutionNarrativeApprovalAction(BaseModel):
    """Audit record describing a decision taken on an approval stage."""

    # purpose: surface approval ladder activity for compliance review
    # inputs: persisted approval action rows
    # outputs: detailed history of decisions for timeline rendering
    # status: pilot
    id: UUID
    stage_id: UUID
    action_type: Literal[
        "approved",
        "rejected",
        "delegated",
        "reassigned",
        "reset",
        "comment",
    ]
    signature: str | None = None
    notes: str | None = None
    actor: UserOut
    delegation_target: UserOut | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="meta")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExecutionNarrativeApprovalStage(BaseModel):
    """Staged approval checkpoint describing role, SLA, and delegates."""

    # purpose: communicate sequenced approval requirements to clients
    # inputs: persisted stage configuration and runtime status
    # outputs: UI ladder representation and audit data
    # status: pilot
    id: UUID
    export_id: UUID
    sequence_index: int
    name: str | None = None
    required_role: str
    status: Literal[
        "pending",
        "in_progress",
        "approved",
        "rejected",
        "delegated",
        "reset",
    ]
    sla_hours: int | None = None
    due_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assignee: UserOut | None = None
    delegated_to: UserOut | None = None
    overdue_notified_at: datetime | None = None
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="meta")
    actions: list[ExecutionNarrativeApprovalAction] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExecutionNarrativeApprovalStageDefinition(BaseModel):
    """Stage configuration supplied when initializing a workflow."""

    # purpose: allow API consumers to declare staged approval ladders
    # inputs: narrative export creation payload
    # outputs: normalized stage blueprint persisted to database
    # status: pilot
    name: str | None = None
    required_role: str
    assignee_id: UUID | None = None
    delegate_id: UUID | None = None
    sla_hours: int | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeWorkflowTemplateStage(BaseModel):
    """Reusable stage blueprint definition stored on templates."""

    # purpose: capture governance-authored approval ladder stages
    # inputs: governance template authoring UI payloads
    # outputs: normalized stage definitions persisted with templates
    # status: draft
    name: str | None = None
    required_role: str
    sla_hours: int | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeWorkflowTemplateBase(BaseModel):
    template_key: str
    name: str
    description: str | None = None
    default_stage_sla_hours: int | None = None
    permitted_roles: list[str] = Field(default_factory=list)
    stage_blueprint: list[ExecutionNarrativeWorkflowTemplateStage] = Field(
        default_factory=list
    )


class ExecutionNarrativeWorkflowTemplateCreate(ExecutionNarrativeWorkflowTemplateBase):
    forked_from_id: UUID | None = None
    publish: bool = False


class ExecutionNarrativeWorkflowTemplateOut(
    ExecutionNarrativeWorkflowTemplateBase
):
    id: UUID
    version: int
    status: str
    is_latest: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    forked_from_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ExecutionNarrativeWorkflowTemplateAssignmentCreate(BaseModel):
    template_id: UUID
    team_id: UUID | None = None
    protocol_template_id: UUID | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeWorkflowTemplateAssignmentOut(BaseModel):
    id: UUID
    template_id: UUID
    team_id: UUID | None = None
    protocol_template_id: UUID | None = None
    created_by_id: UUID
    created_at: datetime
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="meta",
        serialization_alias="metadata",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExecutionNarrativeExport(BaseModel):
    """Markdown export payload capturing execution evidence."""

    # purpose: describe serialized narrative exports for API consumers
    # inputs: generated by create_execution_narrative_export route
    # outputs: metadata and Markdown content for downloads
    # status: pilot
    id: UUID
    execution_id: UUID
    version: int
    format: Literal["markdown"] = "markdown"
    generated_at: datetime
    event_count: int
    content: str
    approval_status: Literal["pending", "approved", "rejected"]
    approval_signature: str | None = None
    approved_at: datetime | None = None
    approval_completed_at: datetime | None = None
    approval_stage_count: int = 0
    workflow_template_id: UUID | None = None
    workflow_template_key: str | None = None
    workflow_template_version: int | None = None
    workflow_template_snapshot: Dict[str, Any] = Field(default_factory=dict)
    current_stage: ExecutionNarrativeApprovalStage | None = None
    current_stage_started_at: datetime | None = None
    requested_by: UserOut
    approved_by: Optional[UserOut] = None
    notes: str | None = None
    approval_stages: list[ExecutionNarrativeApprovalStage] = Field(default_factory=list)
    attachments: list[ExecutionNarrativeExportAttachmentOut] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias='meta')
    artifact_status: Literal[
        "queued",
        "processing",
        "ready",
        "retrying",
        "failed",
        "expired",
    ] = "queued"
    artifact_checksum: str | None = None
    artifact_error: str | None = None
    artifact_file: Optional[FileOut] = None
    artifact_download_path: str | None = None
    artifact_signed_url: str | None = None
    artifact_manifest_digest: str | None = None
    packaging_attempts: int = 0
    packaged_at: datetime | None = None
    retired_at: datetime | None = None
    retention_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExecutionNarrativeExportRequest(BaseModel):
    """Client payload for generating a persisted narrative export."""

    # purpose: capture bundling selections and notes when exporting narratives
    # inputs: export creation request body from console
    # outputs: normalized parameters for export persistence workflow
    # status: pilot
    attachments: List[ExecutionNarrativeAttachmentIn] = Field(default_factory=list)
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    workflow_template_id: UUID | None = None
    approval_stages: list[ExecutionNarrativeApprovalStageDefinition] = Field(
        default_factory=list
    )


class ExecutionNarrativeApprovalRequest(BaseModel):
    """Approval payload recording compliance sign-off."""

    # purpose: update narrative export with approver metadata and signature
    # inputs: approval request body from console
    # outputs: approval status persisted with export record
    # status: pilot
    status: Literal["approved", "rejected"]
    signature: str
    stage_id: UUID | None = None
    approver_id: UUID | None = None
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeApprovalDelegationRequest(BaseModel):
    """Delegation payload enabling reassignment of approval responsibility."""

    # purpose: support dynamic reassignment of approval stages from the UI
    # inputs: delegation request body from console
    # outputs: persisted delegation metadata and history action
    # status: pilot
    delegate_id: UUID
    due_at: datetime | None = None
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeApprovalResetRequest(BaseModel):
    """Reset payload returning a stage to pending for remediation."""

    # purpose: allow remediation loops within approval ladders
    # inputs: reset request body from console
    # outputs: persisted reset action with optional comment
    # status: pilot
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionNarrativeExportHistory(BaseModel):
    """Collection wrapper providing chronological export history."""

    exports: list[ExecutionNarrativeExport] = Field(default_factory=list)


class ExperimentExecutionSessionOut(BaseModel):
    execution: "ProtocolExecutionOut"
    protocol: "ProtocolTemplateOut"
    notebook_entries: list["NotebookEntryOut"]
    inventory_items: list["InventoryItemOut"]
    bookings: list["BookingOut"]
    steps: list[ExperimentStepStatus]
    telemetry_channels: list[EquipmentTelemetryChannel] = Field(default_factory=list)
    anomaly_events: list[ExperimentAnomalySignal] = Field(default_factory=list)
    auto_log_entries: list[ExperimentAutoLogEntry] = Field(default_factory=list)
    timeline_preview: list[ExecutionEventOut] = Field(default_factory=list)


class ExperimentRemediationResult(BaseModel):
    """Outcome metadata for a single remediation action."""

    action: str
    status: Literal["executed", "scheduled", "skipped", "failed"]
    message: str | None = None


class ExperimentRemediationRequest(BaseModel):
    """Request payload describing orchestrator-driven remediation."""

    actions: list[str] = Field(default_factory=list)
    auto: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class ExperimentRemediationResponse(BaseModel):
    """Wrapper delivering remediation results alongside refreshed session state."""

    session: ExperimentExecutionSessionOut
    results: list[ExperimentRemediationResult] = Field(default_factory=list)


class NotificationCreate(BaseModel):
    user_id: UUID
    message: str
    title: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    meta: Dict[str, Any] = Field(default_factory=dict)


class NotificationOut(BaseModel):
    id: UUID
    user_id: UUID
    message: str
    title: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    is_read: bool
    meta: Dict[str, Any] = Field(default_factory=dict)
    action_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class NotificationPreferenceUpdate(BaseModel):
    enabled: bool


class NotificationPreferenceOut(BaseModel):
    id: UUID
    user_id: UUID
    pref_type: str
    channel: str
    enabled: bool
    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsOut(BaseModel):
    digest_frequency: Literal["immediate", "hourly", "daily", "weekly"]
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


class NotificationSettingsUpdate(BaseModel):
    digest_frequency: Optional[Literal["immediate", "hourly", "daily", "weekly"]] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


class SequenceRead(BaseModel):
    id: str
    seq: str
    length: int
    gc_content: float


class SequenceJobOut(BaseModel):
    id: UUID
    status: str
    format: str
    result: list[SequenceRead] | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SequenceAlignmentIn(BaseModel):
    seq1: str
    seq2: str
    mode: str = "global"

class SequenceAlignmentOut(BaseModel):
    aligned_seq1: str
    aligned_seq2: str
    score: float


class RestrictionMapIn(BaseModel):
    sequence: str
    enzymes: list[str]


class RestrictionMapOut(BaseModel):
    map: dict[str, list[int]]


class PrimerDesignIn(BaseModel):
    sequence: str
    size: int = 20


class PrimerInfo(BaseModel):
    sequence: str
    gc_content: float
    tm: float


class PrimerDesignOut(BaseModel):
    forward: PrimerInfo
    reverse: PrimerInfo


class SequenceFeature(BaseModel):
    record_id: str
    type: str
    start: int
    end: int
    strand: int | None
    qualifiers: Dict[str, list[str]]


class ChromatogramOut(BaseModel):
    sequence: str
    traces: Dict[str, list[int]]


class BlastSearchIn(BaseModel):
    query: str
    subject: str
    mode: str = "blastn"


class BlastSearchOut(BaseModel):
    query_aligned: str
    subject_aligned: str
    score: float
    identity: float


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    team_id: Optional[UUID] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    team_id: Optional[UUID] = None


class ProjectOut(ProjectCreate):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectTaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class ProjectTaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None


class ProjectTaskOut(ProjectTaskCreate):
    id: UUID
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None


class CalendarEventOut(CalendarEventCreate):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None


class AnalysisToolCreate(BaseModel):
    name: str
    description: Optional[str] = None
    code: str
    supported_types: list[str] = []


class AnalysisToolOut(AnalysisToolCreate):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ToolRunIn(BaseModel):
    item_id: UUID


class AssistantMessageOut(BaseModel):
    id: UUID
    is_user: bool
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(BaseModel):
    id: UUID
    user_id: UUID
    action: str
    target_type: str | None = None
    target_id: UUID | None = None
    details: Dict[str, Any] = {}
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AuditReportItem(BaseModel):
    action: str
    count: int


class EquipmentCreate(BaseModel):
    name: str
    eq_type: str
    connection_info: Dict[str, Any] = {}
    team_id: UUID | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = None
    eq_type: str | None = None
    connection_info: Dict[str, Any] | None = None
    status: str | None = None
    team_id: UUID | None = None


class EquipmentOut(BaseModel):
    id: UUID
    name: str
    eq_type: str
    connection_info: Dict[str, Any]
    status: str
    team_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EquipmentReadingCreate(BaseModel):
    data: Dict[str, Any]


class EquipmentReadingOut(EquipmentReadingCreate):
    id: UUID
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class EquipmentMaintenanceCreate(BaseModel):
    equipment_id: UUID
    due_date: datetime
    task_type: str = "maintenance"
    description: str | None = None


class EquipmentMaintenanceOut(EquipmentMaintenanceCreate):
    id: UUID
    completed_at: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SOPCreate(BaseModel):
    title: str
    version: int = 1
    content: str
    team_id: UUID | None = None


class SOPOut(SOPCreate):
    id: UUID
    created_by: UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TrainingRecordCreate(BaseModel):
    user_id: UUID
    sop_id: UUID
    equipment_id: UUID
    trained_by: UUID


class TrainingRecordOut(TrainingRecordCreate):
    id: UUID
    trained_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssistantQuestion(BaseModel):
    question: str


class InventoryForecastItem(BaseModel):
    item_id: UUID
    name: str
    projected_days: float | None = None


class MaterialSuggestion(BaseModel):
    id: UUID
    name: str


class ProtocolSuggestion(BaseModel):
    protocol_id: UUID
    protocol_name: str
    materials: list[MaterialSuggestion]



class ItemTypeCount(BaseModel):
    item_type: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class TrendingProtocol(BaseModel):
    template_id: UUID
    template_name: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class TrendingArticle(BaseModel):
    article_id: UUID
    title: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class TrendingItem(BaseModel):
    item_id: UUID
    name: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class TrendingThread(BaseModel):
    thread_id: UUID
    title: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class TrendingPost(BaseModel):
    post_id: UUID
    content: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class PubMedQuery(BaseModel):
    query: str
    limit: int = 5


class PubMedArticle(BaseModel):
    id: str
    title: str


class ComplianceRecordCreate(BaseModel):
    item_id: UUID | None = None
    record_type: str
    status: str = "pending"
    notes: str | None = None


class ComplianceRecordUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class ComplianceRecordOut(BaseModel):
    id: UUID
    item_id: UUID | None = None
    user_id: UUID | None = None
    record_type: str
    status: str
    notes: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class KnowledgeArticleCreate(BaseModel):
    title: str
    content: str
    tags: list[str] | None = None
    is_public: bool = False


class KnowledgeArticleUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    is_public: bool | None = None


class KnowledgeArticleOut(BaseModel):
    id: UUID
    title: str
    content: str
    tags: list[str] | None = None
    is_public: bool = False
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExperimentDesignOut(BaseModel):
    protocol: ProtocolSuggestion | None = None
    articles: list[KnowledgeArticleOut] = []
    message: str


class WorkflowStep(BaseModel):
    type: str
    id: UUID
    condition: str | None = None


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    steps: list[WorkflowStep]


class WorkflowOut(WorkflowCreate):
    id: UUID
    created_by: UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionCreate(BaseModel):
    workflow_id: UUID
    item_id: UUID


class WorkflowExecutionUpdate(BaseModel):
    status: str | None = None
    result: list[Any] | None = None


class WorkflowExecutionOut(BaseModel):
    id: UUID
    workflow_id: UUID
    item_id: UUID
    run_by: UUID | None = None
    status: str
    result: list[Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LabCreate(BaseModel):
    name: str
    description: str | None = None


class LabOut(LabCreate):
    id: UUID
    owner_id: UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LabConnectionCreate(BaseModel):
    target_lab: UUID


class LabConnectionOut(BaseModel):
    id: UUID
    from_lab: UUID
    to_lab: UUID
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResourceShareCreate(BaseModel):
    resource_id: UUID
    to_lab: UUID
    start_date: datetime | None = None
    end_date: datetime | None = None


class ResourceShareOut(BaseModel):
    id: UUID
    resource_id: UUID
    from_lab: UUID
    to_lab: UUID
    status: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MarketplaceListingCreate(BaseModel):
    item_id: UUID
    price: int | None = None
    description: str | None = None


class MarketplaceListingOut(BaseModel):
    id: UUID
    item_id: UUID
    seller_id: UUID
    price: int | None = None
    description: str | None = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MarketplaceRequestCreate(BaseModel):
    message: str | None = None


class MarketplaceRequestOut(BaseModel):
    id: UUID
    listing_id: UUID
    buyer_id: UUID
    message: str | None = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    content: str


class PostOut(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FollowOut(BaseModel):
    follower_id: UUID
    followed_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostReportCreate(BaseModel):
    reason: str


class PostReportOut(BaseModel):
    id: UUID
    post_id: UUID
    reporter_id: UUID
    reason: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostLikeOut(BaseModel):
    post_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProtocolStarOut(BaseModel):
    protocol_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeArticleStarOut(BaseModel):
    article_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ForumThreadCreate(BaseModel):
    title: str


class ForumThreadOut(BaseModel):
    id: UUID
    title: str
    created_by: UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ForumPostCreate(BaseModel):
    content: str


class ForumPostOut(BaseModel):
    id: UUID
    thread_id: UUID
    user_id: UUID | None = None
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceListingCreate(BaseModel):
    name: str
    description: str | None = None
    price: int | None = None


class ServiceListingOut(BaseModel):
    id: UUID
    provider_id: UUID
    name: str
    description: str | None = None
    price: int | None = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceRequestCreate(BaseModel):
    item_id: UUID | None = None
    message: str | None = None


class ServiceRequestOut(BaseModel):
    id: UUID
    listing_id: UUID
    requester_id: UUID
    item_id: UUID | None = None
    message: str | None = None
    result_file_id: UUID | None = None
    payment_status: str | None = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ItemTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ItemTypeOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


EquipmentTelemetryChannel.model_rebuild()
ExecutionEventOut.model_rebuild()
ExecutionNarrativeExportAttachmentOut.model_rebuild()
ExecutionNarrativeApprovalAction.model_rebuild()
ExecutionNarrativeApprovalStage.model_rebuild()
ExecutionNarrativeExport.model_rebuild()
ExecutionNarrativeExportHistory.model_rebuild()
ExperimentTimelinePage.model_rebuild()
ExperimentExecutionSessionOut.model_rebuild()
ExperimentRemediationResult.model_rebuild()
ExperimentRemediationRequest.model_rebuild()
ExperimentRemediationResponse.model_rebuild()
