"""Pydantic schemas consolidating backend API contracts."""

# purpose: aggregate request and response schemas for FastAPI surfaces and services
# status: transitional
# related_docs: docs/README.md

from datetime import datetime, time
from typing import Optional, Any, Dict, Literal, List
from pydantic import BaseModel, EmailStr, ConfigDict, Field, model_validator
from uuid import UUID

from .dna_assets import (
    DNAAnnotationOut,
    DNAAnnotationPayload,
    DNAAssetCreate,
    DNAAssetDiffResponse,
    DNAAssetGovernanceUpdate,
    DNAAssetGuardrailEventOut,
    DNAAssetGuardrailHeuristics,
    DNAAssetKineticsSummary,
    DNAAssetSummary,
    DNAAssetVersionCreate,
    DNAAssetVersionOut,
)
from .sequence_toolkit import (
    AssemblySimulationConfig,
    AssemblySimulationResult,
    PrimerDesignConfig,
    PrimerDesignResponse,
    QCConfig,
    QCReportResponse,
    RestrictionDigestConfig,
    RestrictionDigestResponse,
    SequenceToolkitProfile,
)


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


class ExperimentPreviewResourceOverrides(BaseModel):
    # purpose: allow scientists to model alternative resource availability
    # inputs: override identifiers supplied by preview requests
    # outputs: normalized identifier lists for simulation enrichment
    # status: pilot
    inventory_item_ids: list[UUID] = Field(default_factory=list)
    booking_ids: list[UUID] = Field(default_factory=list)
    equipment_ids: list[UUID] = Field(default_factory=list)


class ExperimentPreviewStageOverride(BaseModel):
    # purpose: enable temporary adjustments to stage assignments and SLAs
    # inputs: per-stage override payloads from preview consumers
    # outputs: normalized override configuration for simulation engine
    # status: pilot
    index: int
    assignee_id: UUID | None = None
    delegate_id: UUID | None = None
    sla_hours: int | None = None


class ExperimentPreviewRequest(BaseModel):
    # purpose: capture snapshot bindings and optional simulation overrides
    # inputs: immutable template snapshot id, optional overrides for preview
    # outputs: structured preview parameters for backend orchestration
    # status: pilot
    workflow_template_snapshot_id: UUID
    resource_overrides: ExperimentPreviewResourceOverrides | None = None
    stage_overrides: list[ExperimentPreviewStageOverride] = Field(default_factory=list)


class ExperimentPreviewStageInsight(BaseModel):
    # purpose: surface readiness state and SLA projections per stage
    # inputs: simulation evaluation results for a stage
    # outputs: UI-friendly insight payload for preview diff views
    # status: pilot
    index: int
    name: str | None = None
    required_role: str
    status: Literal["ready", "blocked"]
    sla_hours: int | None = None
    projected_due_at: datetime | None = None
    blockers: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    auto_triggers: list[str] = Field(default_factory=list)
    assignee_id: UUID | None = None
    delegate_id: UUID | None = None
    mapped_step_indexes: list[int] = Field(default_factory=list)
    gate_keys: list[str] = Field(default_factory=list)
    baseline_status: Literal["ready", "blocked"] | None = None
    baseline_sla_hours: int | None = None
    baseline_projected_due_at: datetime | None = None
    baseline_assignee_id: UUID | None = None
    baseline_delegate_id: UUID | None = None
    baseline_blockers: list[str] = Field(default_factory=list)
    delta_status: Literal["cleared", "regressed", "unchanged"] | None = None
    delta_sla_hours: int | None = None
    delta_projected_due_minutes: int | None = None
    delta_new_blockers: list[str] = Field(default_factory=list)
    delta_resolved_blockers: list[str] = Field(default_factory=list)


class ExperimentPreviewResponse(BaseModel):
    # purpose: deliver scientist-facing ladder simulation and narrative preview
    # inputs: execution identifier, snapshot binding, stage insights, narrative
    # outputs: preview metadata for diff viewers and governance storytelling
    # status: pilot
    execution_id: UUID
    snapshot_id: UUID
    baseline_snapshot_id: UUID | None = None
    generated_at: datetime
    template_name: str | None = None
    template_version: int | None = None
    stage_insights: list[ExperimentPreviewStageInsight] = Field(default_factory=list)
    narrative_preview: str
    resource_warnings: list[str] = Field(default_factory=list)


class GovernanceAnalyticsSlaSample(BaseModel):
    # purpose: capture predicted vs actual SLA outcomes for governance preview stages
    # inputs: preview projection timestamps and execution completion telemetry
    # outputs: per-stage SLA delta metrics powering analytics visualisations
    # status: pilot
    stage_index: int
    predicted_due_at: datetime | None = None
    actual_completed_at: datetime | None = None
    delta_minutes: int | None = None
    within_target: bool | None = None


class GovernanceAnalyticsLatencyBand(BaseModel):
    # purpose: codify reviewer latency histogram buckets for governance analytics
    # inputs: bucket label, inclusive start minute, exclusive end minute, sample count
    # outputs: structured latency band metadata for reviewer dashboards
    # status: pilot
    label: str
    start_minutes: int | None = None
    end_minutes: int | None = None
    count: int = 0


class GovernanceReviewerCadenceSummary(BaseModel):
    # purpose: express RBAC-safe reviewer cadence metrics for throughput analytics
    # inputs: aggregated lifecycle samples derived from compute_governance_analytics
    # outputs: reviewer-centric payload powering cadence heatmaps and alerting primitives
    # status: pilot
    reviewer_id: UUID
    reviewer_email: EmailStr | None = None
    reviewer_name: str | None = None
    assignment_count: int = 0
    completion_count: int = 0
    pending_count: int = 0
    load_band: Literal["light", "steady", "saturated"] = "light"
    average_latency_minutes: float | None = None
    latency_p50_minutes: float | None = None
    latency_p90_minutes: float | None = None
    latency_bands: list[GovernanceAnalyticsLatencyBand] = Field(default_factory=list)
    blocked_ratio_trailing: float | None = None
    churn_signal: float | None = None
    rollback_precursor_count: int = 0
    publish_streak: int = 0
    last_publish_at: datetime | None = None
    streak_alert: bool = False


class GovernanceReviewerLoadBandCounts(BaseModel):
    # purpose: capture reviewer load distribution for governance cadence payloads
    # inputs: reviewer cadence aggregation buckets (light/steady/saturated)
    # outputs: reusable load band histogram for analytics dashboards
    # status: pilot
    light: int = 0
    steady: int = 0
    saturated: int = 0


class GovernanceReviewerCadenceTotals(BaseModel):
    # purpose: deliver aggregate reviewer cadence guardrails for staffing insights
    # inputs: reviewer cadence aggregation outputs from governance analytics
    # outputs: summary metrics powering alert badges and density heatmaps
    # status: pilot
    reviewer_count: int = 0
    streak_alert_count: int = 0
    reviewer_latency_p50_minutes: float | None = None
    reviewer_latency_p90_minutes: float | None = None
    load_band_counts: GovernanceReviewerLoadBandCounts = Field(default_factory=GovernanceReviewerLoadBandCounts)


class GovernanceScenarioOverrideAggregate(BaseModel):
    # purpose: summarise override lineage counts for a scenario anchor
    # status: pilot

    scenario_id: UUID | None = None
    scenario_name: str | None = None
    folder_name: str | None = None
    executed_count: int = 0
    reversed_count: int = 0
    net_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GovernanceNotebookOverrideAggregate(BaseModel):
    # purpose: track notebook-linked override lineage deltas for analytics heatmaps
    # status: pilot

    notebook_entry_id: UUID | None = None
    notebook_title: str | None = None
    execution_id: UUID | None = None
    executed_count: int = 0
    reversed_count: int = 0
    net_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GovernanceOverrideLineageAggregates(BaseModel):
    # purpose: bundle aggregated override lineage buckets for analytics surfaces
    # status: pilot

    scenarios: list[GovernanceScenarioOverrideAggregate] = Field(default_factory=list)
    notebooks: list[GovernanceNotebookOverrideAggregate] = Field(default_factory=list)


class GovernanceAnalyticsPreviewSummary(BaseModel):
    # purpose: summarise governance preview telemetry blended with execution history and baseline lifecycle metrics
    # inputs: aggregated metrics produced by compute_governance_analytics
    # outputs: dashboard-ready analytics payload for experiment console panels
    # status: pilot
    execution_id: UUID
    preview_event_id: UUID
    snapshot_id: UUID | None = None
    baseline_snapshot_id: UUID | None = None
    generated_at: datetime
    stage_count: int
    blocked_stage_count: int
    blocked_ratio: float
    overrides_applied: int
    override_actions_executed: int = 0
    override_actions_reversed: int = 0
    override_cooldown_minutes: float | None = None
    new_blocker_count: int
    resolved_blocker_count: int
    ladder_load: float
    sla_within_target_ratio: float | None = None
    mean_sla_delta_minutes: float | None = None
    sla_samples: list[GovernanceAnalyticsSlaSample] = Field(default_factory=list)
    blocker_heatmap: list[int] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"]
    baseline_version_count: int = 0
    approval_latency_minutes: float | None = None
    publication_cadence_days: float | None = None
    rollback_count: int = 0
    blocker_churn_index: float | None = None


class GovernanceAnalyticsTotals(BaseModel):
    # purpose: provide aggregate governance analytics context for dashboards including lifecycle cadence
    # inputs: preview summary collection metrics
    # outputs: dataset totals to render trend summaries and KPIs
    # status: pilot
    preview_count: int
    average_blocked_ratio: float
    total_new_blockers: int
    total_resolved_blockers: int
    average_sla_within_target_ratio: float | None = None
    total_baseline_versions: int
    total_rollbacks: int
    average_approval_latency_minutes: float | None = None
    average_publication_cadence_days: float | None = None
    reviewer_count: int = 0
    streak_alert_count: int = 0
    reviewer_latency_p50_minutes: float | None = None
    reviewer_latency_p90_minutes: float | None = None
    reviewer_load_band_counts: GovernanceReviewerLoadBandCounts = Field(default_factory=GovernanceReviewerLoadBandCounts)


class GovernanceAnalyticsReport(BaseModel):
    # purpose: deliver structured governance analytics response payloads
    # inputs: preview summary list, reviewer cadence aggregates, and totals
    # outputs: API response consumed by governance analytics clients
    # status: pilot
    results: list[GovernanceAnalyticsPreviewSummary] = Field(default_factory=list)
    reviewer_cadence: list[GovernanceReviewerCadenceSummary] = Field(default_factory=list)
    totals: GovernanceAnalyticsTotals
    lineage_summary: GovernanceOverrideLineageAggregates = Field(
        default_factory=GovernanceOverrideLineageAggregates
    )
    meta: Dict[str, Any] = Field(default_factory=dict)


class GovernanceGuardrailStageSnapshot(BaseModel):
    # purpose: represent baseline or simulated stage state for guardrail simulations
    status: str
    sla_hours: int | None = None
    projected_due_at: datetime | None = None
    blockers: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    auto_triggers: list[str] = Field(default_factory=list)
    assignee_id: UUID | None = None
    delegate_id: UUID | None = None


class GovernanceGuardrailStageComparison(BaseModel):
    # purpose: capture baseline vs simulated stage states for guardrail evaluation
    index: int
    name: str | None = None
    required_role: str
    mapped_step_indexes: list[int] = Field(default_factory=list)
    gate_keys: list[str] = Field(default_factory=list)
    baseline: GovernanceGuardrailStageSnapshot
    simulated: GovernanceGuardrailStageSnapshot


class GovernanceGuardrailSimulationRequest(BaseModel):
    # purpose: request payload for guardrail simulation evaluation
    execution_id: UUID
    comparisons: list[GovernanceGuardrailStageComparison] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceGuardrailSummary(BaseModel):
    # purpose: expose aggregate guardrail status and contributing signals
    state: Literal["clear", "blocked"]
    reasons: list[str] = Field(default_factory=list)
    regressed_stage_indexes: list[int] = Field(default_factory=list)
    projected_delay_minutes: int = 0


class GovernanceGuardrailSimulationRecord(BaseModel):
    # purpose: return persisted guardrail simulation summaries
    id: UUID
    execution_id: UUID
    actor: UserOut | None = None
    summary: GovernanceGuardrailSummary
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    state: Literal["clear", "blocked"]
    projected_delay_minutes: int

    model_config = ConfigDict(from_attributes=True)


class GovernanceGuardrailQueueEntry(BaseModel):
    # purpose: surface sanitized packaging queue telemetry for guardrail dashboards
    export_id: UUID
    execution_id: UUID
    version: int | None = None
    state: str = "unknown"
    event: str | None = None
    approval_status: str
    artifact_status: str
    packaging_attempts: int = 0
    guardrail_state: Literal["clear", "blocked"] | None = None
    projected_delay_minutes: int | None = None
    pending_stage_id: UUID | None = None
    pending_stage_index: int | None = None
    pending_stage_status: str | None = None
    pending_stage_due_at: datetime | None = None
    updated_at: datetime | None = None
    context: Dict[str, Any] = Field(default_factory=dict)


class GovernanceGuardrailHealthTotals(BaseModel):
    # purpose: summarize guardrail queue state counts for operator dashboards
    total_exports: int = 0
    blocked: int = 0
    awaiting_approval: int = 0
    queued: int = 0
    ready: int = 0
    failed: int = 0


class GovernanceGuardrailHealthReport(BaseModel):
    # purpose: deliver guardrail queue health payloads for governance workspaces
    totals: GovernanceGuardrailHealthTotals = Field(
        default_factory=GovernanceGuardrailHealthTotals
    )
    state_breakdown: Dict[str, int] = Field(default_factory=dict)
    queue: list[GovernanceGuardrailQueueEntry] = Field(default_factory=list)


class GovernanceReviewerCadenceReport(BaseModel):
    # purpose: expose lean reviewer cadence analytics payloads for staffing dashboards
    # inputs: reviewer cadence summaries and aggregate guardrails filtered via RBAC
    # outputs: lightweight report consumed when requesting view=reviewer
    # status: pilot
    reviewers: list[GovernanceReviewerCadenceSummary] = Field(default_factory=list)
    totals: GovernanceReviewerCadenceTotals


# purpose: helper to normalise reviewer load band histograms for cadence payloads
def build_reviewer_load_band_counts(
    *, light: int = 0, steady: int = 0, saturated: int = 0
) -> GovernanceReviewerLoadBandCounts:
    return GovernanceReviewerLoadBandCounts(
        light=light, steady=steady, saturated=saturated
    )


# purpose: construct GovernanceReviewerCadenceSummary objects from aggregation primitives
def build_reviewer_cadence_summary(
    *,
    reviewer_id: UUID,
    reviewer_email: EmailStr | None = None,
    reviewer_name: str | None = None,
    assignment_count: int = 0,
    completion_count: int = 0,
    pending_count: int = 0,
    load_band: Literal["light", "steady", "saturated"] = "light",
    average_latency_minutes: float | None = None,
    latency_p50_minutes: float | None = None,
    latency_p90_minutes: float | None = None,
    latency_bands: list[GovernanceAnalyticsLatencyBand] | None = None,
    blocked_ratio_trailing: float | None = None,
    churn_signal: float | None = None,
    rollback_precursor_count: int = 0,
    publish_streak: int = 0,
    last_publish_at: datetime | None = None,
    streak_alert: bool = False,
) -> GovernanceReviewerCadenceSummary:
    return GovernanceReviewerCadenceSummary(
        reviewer_id=reviewer_id,
        reviewer_email=reviewer_email,
        reviewer_name=reviewer_name,
        assignment_count=assignment_count,
        completion_count=completion_count,
        pending_count=pending_count,
        load_band=load_band,
        average_latency_minutes=average_latency_minutes,
        latency_p50_minutes=latency_p50_minutes,
        latency_p90_minutes=latency_p90_minutes,
        latency_bands=latency_bands or [],
        blocked_ratio_trailing=blocked_ratio_trailing,
        churn_signal=churn_signal,
        rollback_precursor_count=rollback_precursor_count,
        publish_streak=publish_streak,
        last_publish_at=last_publish_at,
        streak_alert=streak_alert,
    )


# purpose: build GovernanceReviewerCadenceTotals with consistent load band payloads
def build_reviewer_cadence_totals(
    *,
    reviewer_count: int,
    streak_alert_count: int,
    reviewer_latency_p50_minutes: float | None,
    reviewer_latency_p90_minutes: float | None,
    load_band_counts: GovernanceReviewerLoadBandCounts
    | dict[str, int],
) -> GovernanceReviewerCadenceTotals:
    counts_model = (
        load_band_counts
        if isinstance(load_band_counts, GovernanceReviewerLoadBandCounts)
        else GovernanceReviewerLoadBandCounts(**load_band_counts)
    )
    return GovernanceReviewerCadenceTotals(
        reviewer_count=reviewer_count,
        streak_alert_count=streak_alert_count,
        reviewer_latency_p50_minutes=reviewer_latency_p50_minutes,
        reviewer_latency_p90_minutes=reviewer_latency_p90_minutes,
        load_band_counts=counts_model,
    )


# purpose: central mapper for GovernanceReviewerCadenceReport responses
def build_reviewer_cadence_report(
    reviewers: list[GovernanceReviewerCadenceSummary],
    totals: GovernanceReviewerCadenceTotals,
) -> GovernanceReviewerCadenceReport:
    return GovernanceReviewerCadenceReport(reviewers=reviewers, totals=totals)


class GovernanceOverrideRecommendation(BaseModel):
    # purpose: express deterministic governance override advisories for operators
    # inputs: rule identifier, reviewer context, action summary, metric payload
    # outputs: override recommendation cards consumed by experiment console surfaces
    # status: pilot
    recommendation_id: str
    rule_key: str
    action: Literal["reassign", "cooldown", "escalate"]
    priority: Literal["low", "medium", "high"]
    summary: str
    detail: str | None = None
    reviewer_id: UUID | None = None
    reviewer_name: str | None = None
    reviewer_email: EmailStr | None = None
    triggered_at: datetime
    related_execution_ids: list[UUID] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    allow_opt_out: bool = True


class GovernanceOverrideRecommendationReport(BaseModel):
    # purpose: bundle governance override recommendations with generation metadata
    # inputs: recommendation collection, generation timestamp, optional context
    # outputs: response payload for governance recommendation routes
    # status: pilot
    generated_at: datetime
    recommendations: list[GovernanceOverrideRecommendation] = Field(default_factory=list)


# purpose: construct GovernanceOverrideRecommendation payloads with consistent defaults
def build_governance_override_recommendation(
    *,
    recommendation_id: str,
    rule_key: str,
    action: Literal["reassign", "cooldown", "escalate"],
    priority: Literal["low", "medium", "high"],
    summary: str,
    detail: str | None,
    reviewer_id: UUID | None,
    reviewer_name: str | None,
    reviewer_email: EmailStr | None,
    triggered_at: datetime,
    related_execution_ids: list[UUID],
    metrics: Dict[str, Any],
    allow_opt_out: bool = True,
) -> GovernanceOverrideRecommendation:
    return GovernanceOverrideRecommendation(
        recommendation_id=recommendation_id,
        rule_key=rule_key,
        action=action,
        priority=priority,
        summary=summary,
        detail=detail,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer_name,
        reviewer_email=reviewer_email,
        triggered_at=triggered_at,
        related_execution_ids=related_execution_ids,
        metrics=metrics,
        allow_opt_out=allow_opt_out,
    )


# purpose: assemble GovernanceOverrideRecommendationReport from recommendations and timestamp


class GovernanceActorSummary(BaseModel):
    # purpose: minimal actor context for governance timeline entries
    # status: pilot

    id: UUID | None = None
    name: str | None = None
    email: str | None = None


class GovernanceScenarioLineage(BaseModel):
    # purpose: convey authored scenario provenance for override lineage widgets
    # status: pilot

    id: UUID
    name: str | None = None
    folder_id: UUID | None = None
    folder_name: str | None = None
    owner_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class GovernanceNotebookLineage(BaseModel):
    # purpose: surface notebook provenance for override lineage blocks
    # status: pilot

    id: UUID
    title: str | None = None
    execution_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class GovernanceOverrideLineageContext(BaseModel):
    # purpose: bundle structured override lineage details for timeline consumers
    # status: pilot

    scenario: GovernanceScenarioLineage | None = None
    notebook_entry: GovernanceNotebookLineage | None = None
    captured_at: datetime | None = None
    captured_by: GovernanceActorSummary | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="meta")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GovernanceOverrideReversalDiff(BaseModel):
    # purpose: express before/after delta for override reversal attributes
    # status: pilot

    key: str
    before: Any | None = None
    after: Any | None = None


class GovernanceOverrideReversalDetail(BaseModel):
    # purpose: serialize structured override reversal events for clients
    # status: pilot

    id: UUID
    override_id: UUID
    baseline_id: UUID | None = None
    actor: GovernanceActorSummary | None = None
    created_at: datetime
    cooldown_expires_at: datetime | None = None
    cooldown_window_minutes: int | None = None
    diffs: list[GovernanceOverrideReversalDiff] = Field(default_factory=list)
    previous_detail: Dict[str, Any] = Field(default_factory=dict)
    current_detail: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GovernanceOverrideLineagePayload(BaseModel):
    # purpose: validate lineage payload supplied during override actions
    # status: pilot

    scenario_id: UUID | None = None
    notebook_entry_id: UUID | None = None
    notebook_entry_version_id: UUID | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_scope(self) -> "GovernanceOverrideLineagePayload":
        if self.scenario_id is None and self.notebook_entry_id is None:
            raise ValueError(
                "Override lineage payload requires scenario or notebook provenance"
            )
        return self


class GovernanceOverrideActionRequest(BaseModel):
    # purpose: validate override action invocations for governance routes
    # inputs: execution scope, optional baseline context, reviewer targets, metadata
    # outputs: normalized payload ready for override workflow execution
    # status: pilot
    execution_id: UUID
    action: Literal["reassign", "cooldown", "escalate"]
    baseline_id: UUID | None = None
    target_reviewer_id: UUID | None = None
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    lineage: GovernanceOverrideLineagePayload | None = None

    @model_validator(mode="after")
    def _validate_action(self) -> "GovernanceOverrideActionRequest":
        if self.action == "reassign":
            if self.baseline_id is None:
                raise ValueError("Reassign overrides require a baseline identifier")
            if self.target_reviewer_id is None:
                raise ValueError("Reassign overrides require a target reviewer")
        if self.lineage is None:
            raise ValueError("Override actions require a lineage payload")
        return self


class GovernanceOverrideReverseRequest(BaseModel):
    # purpose: validate governance override reversals triggered by operators
    # inputs: execution identifier, optional baseline linkage, reversal notes, metadata
    # outputs: normalized payload for reversal workflow execution
    # status: pilot
    execution_id: UUID
    baseline_id: UUID | None = None
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceOverrideActionOutcome(BaseModel):
    # purpose: serialize override action records for governance clients
    # inputs: GovernanceOverrideAction ORM instances with optional metadata
    # outputs: API payload describing action status and lineage links
    # status: pilot
    id: UUID
    recommendation_id: str
    action: Literal["reassign", "cooldown", "escalate"]
    status: Literal["accepted", "declined", "executed", "reversed"]
    execution_id: UUID | None = None
    baseline_id: UUID | None = None
    target_reviewer_id: UUID | None = None
    actor_id: UUID
    reversible: bool = False
    notes: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="meta")
    created_at: datetime
    updated_at: datetime
    lineage: GovernanceOverrideLineageContext | None = None
    reversal_event: GovernanceOverrideReversalDetail | None = Field(
        default=None,
        alias="reversal_event_payload",
        validation_alias="reversal_event_payload",
        serialization_alias="reversal_event",
    )
    cooldown_expires_at: datetime | None = None
    cooldown_window_minutes: int | None = None
    reversal_lock_token: str | None = None
    reversal_lock_tier_key: str | None = None
    reversal_lock_tier: str | None = None
    reversal_lock_tier_level: int | None = None
    reversal_lock_scope: str | None = None
    reversal_lock_actor_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


def build_governance_override_report(
    *,
    generated_at: datetime,
    recommendations: list[GovernanceOverrideRecommendation],
) -> GovernanceOverrideRecommendationReport:
    return GovernanceOverrideRecommendationReport(
        generated_at=generated_at,
        recommendations=recommendations,
    )


class BaselineLifecycleLabel(BaseModel):
    # purpose: express structured metadata tags applied to baseline submissions
    # status: draft
    key: str
    value: str


class GovernanceBaselineEventOut(BaseModel):
    # purpose: surface auditable baseline lifecycle transitions
    # status: draft
    id: UUID
    baseline_id: UUID
    action: str
    notes: str | None = None
    detail: dict[str, Any]
    performed_by_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GovernanceBaselineVersionOut(BaseModel):
    # purpose: return enriched baseline lifecycle records to clients
    # status: draft
    id: UUID
    execution_id: UUID
    template_id: UUID | None = None
    team_id: UUID | None = None
    name: str
    description: str | None = None
    status: str
    labels: list[BaselineLifecycleLabel] = Field(default_factory=list)
    reviewer_ids: list[UUID] = Field(default_factory=list)
    version_number: int | None = None
    is_current: bool
    submitted_by_id: UUID
    submitted_at: datetime
    reviewed_by_id: UUID | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    published_by_id: UUID | None = None
    published_at: datetime | None = None
    publish_notes: str | None = None
    rollback_of_id: UUID | None = None
    rolled_back_by_id: UUID | None = None
    rolled_back_at: datetime | None = None
    rollback_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    events: list[GovernanceBaselineEventOut] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class GovernanceBaselineCollection(BaseModel):
    # purpose: wrap baseline collections for predictable API responses
    # status: draft
    items: list[GovernanceBaselineVersionOut] = Field(default_factory=list)


class BaselineSubmissionRequest(BaseModel):
    # purpose: validate baseline submission payloads from experiment console
    # status: draft
    execution_id: UUID
    name: str
    description: str | None = None
    reviewer_ids: list[UUID] = Field(default_factory=list)
    labels: list[BaselineLifecycleLabel] = Field(default_factory=list)


class BaselineReviewRequest(BaseModel):
    # purpose: capture reviewer decisions with optional notes
    # status: draft
    decision: Literal["approve", "reject"]
    notes: str | None = None


class BaselinePublishRequest(BaseModel):
    # purpose: accept publishing confirmations and notes
    # status: draft
    notes: str | None = None


class BaselineRollbackRequest(BaseModel):
    # purpose: gather rollback justifications and optional target restoration
    # status: draft
    reason: str
    target_version_id: UUID | None = None


class ExperimentScenarioFolder(BaseModel):
    # purpose: describe scenario folder metadata for workspace navigation
    # status: pilot
    id: UUID
    execution_id: UUID
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    team_id: UUID | None = None
    visibility: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExperimentScenarioFolderCreate(BaseModel):
    # purpose: capture creation payload for scenario folders
    # status: pilot
    name: str
    description: str | None = None
    visibility: Literal["private", "team", "execution"] = "private"
    team_id: UUID | None = None


class ExperimentScenarioFolderUpdate(BaseModel):
    # purpose: allow selective folder metadata updates
    # status: pilot
    name: str | None = None
    description: str | None = None
    visibility: Literal["private", "team", "execution"] | None = None
    team_id: UUID | None = None


class ExperimentScenarioBase(BaseModel):
    # purpose: normalize persisted scenario payloads for CRUD operations
    # inputs: scenario metadata including snapshot binding and overrides
    # outputs: sanitized override payload suitable for storage and preview invocation
    # status: pilot
    name: str
    description: str | None = None
    workflow_template_snapshot_id: UUID
    folder_id: UUID | None = None
    is_shared: bool = False
    shared_team_ids: list[UUID] = Field(default_factory=list)
    resource_overrides: ExperimentPreviewResourceOverrides | None = None
    stage_overrides: list[ExperimentPreviewStageOverride] = Field(default_factory=list)
    expires_at: datetime | None = None
    timeline_event_id: UUID | None = None


class ExperimentScenarioCreate(ExperimentScenarioBase):
    # purpose: capture scenario creation payload from scientist workspace
    # status: pilot
    pass


class ExperimentScenarioUpdate(BaseModel):
    # purpose: allow selective scenario metadata updates
    # status: pilot
    name: str | None = None
    description: str | None = None
    workflow_template_snapshot_id: UUID | None = None
    resource_overrides: ExperimentPreviewResourceOverrides | None = None
    stage_overrides: list[ExperimentPreviewStageOverride] | None = None
    folder_id: UUID | None = None
    is_shared: bool | None = None
    shared_team_ids: list[UUID] | None = None
    expires_at: datetime | None = None
    timeline_event_id: UUID | None = None
    transfer_owner_id: UUID | None = None


class ExperimentScenario(BaseModel):
    # purpose: expose persisted scenario metadata to clients
    # status: pilot
    id: UUID
    execution_id: UUID
    owner_id: UUID
    team_id: UUID | None = None
    workflow_template_snapshot_id: UUID
    name: str
    description: str | None = None
    resource_overrides: ExperimentPreviewResourceOverrides | None = None
    stage_overrides: list[ExperimentPreviewStageOverride] = Field(default_factory=list)
    cloned_from_id: UUID | None = None
    folder_id: UUID | None = None
    is_shared: bool
    shared_team_ids: list[UUID] = Field(default_factory=list)
    expires_at: datetime | None = None
    timeline_event_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExperimentScenarioCloneRequest(BaseModel):
    # purpose: allow naming overrides when cloning scenarios
    # status: pilot
    name: str | None = None
    description: str | None = None


class ExperimentScenarioSnapshot(BaseModel):
    # purpose: summarize workflow template snapshots for scenario workspace selection
    # status: pilot
    id: UUID
    template_id: UUID
    template_key: str
    version: int
    status: str
    captured_at: datetime
    captured_by_id: UUID
    template_name: str | None = None


class ExperimentScenarioExecutionSummary(BaseModel):
    # purpose: provide minimal execution metadata for workspace sidebar context
    # status: pilot
    id: UUID
    template_id: UUID | None = None
    template_name: str | None = None
    template_version: str | None = None
    run_by_id: UUID | None = None
    status: str | None = None


class ExperimentScenarioWorkspace(BaseModel):
    # purpose: bundle execution context, available snapshots, and saved scenarios
    # status: pilot
    execution: ExperimentScenarioExecutionSummary
    snapshots: list[ExperimentScenarioSnapshot] = Field(default_factory=list)
    scenarios: list[ExperimentScenario] = Field(default_factory=list)
    folders: list[ExperimentScenarioFolder] = Field(default_factory=list)


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


class GovernanceCoachingNoteBase(BaseModel):
    """Base payload for governance coaching note mutations."""

    # purpose: capture shared fields for coaching note create/update operations
    # inputs: API payloads for governance coaching note CRUD endpoints
    # outputs: validated request payloads with metadata defaults
    # status: experimental

    body: str = Field(..., min_length=1)
    parent_id: UUID | None = None
    baseline_id: UUID | None = None
    execution_id: UUID | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceCoachingNoteCreate(GovernanceCoachingNoteBase):
    """Request payload for creating a governance coaching note."""

    # purpose: differentiate creation-time payload semantics from updates
    # status: experimental


class GovernanceCoachingNoteUpdate(BaseModel):
    """Request payload for updating a governance coaching note."""

    # purpose: allow partial updates to coaching note content and moderation state
    # inputs: API patch payloads from governance console
    # outputs: sanitized update directives for persistence layer
    # status: experimental

    body: str | None = Field(default=None)
    moderation_state: Literal["draft", "published", "flagged", "resolved", "removed"] | None = None
    metadata: Dict[str, Any] | None = None


class GovernanceCoachingNoteModerationAction(BaseModel):
    """Request payload for moderation-specific coaching note transitions."""

    # purpose: capture optional operator rationale and metadata updates
    # inputs: targeted moderation PATCH payloads from governance console
    # outputs: sanitized arguments for moderation helpers
    # status: experimental

    reason: str | None = None
    metadata: Dict[str, Any] | None = None


class GovernanceCoachingNoteOut(BaseModel):
    """Serialized governance coaching note for API responses."""

    # purpose: expose threaded coaching context in governance APIs
    # inputs: ORM GovernanceCoachingNote rows
    # outputs: response payload consumed by governance console UI
    # status: experimental

    id: UUID
    override_id: UUID
    baseline_id: UUID | None = None
    execution_id: UUID | None = None
    parent_id: UUID | None = None
    thread_root_id: UUID | None = None
    moderation_state: Literal["draft", "published", "flagged", "resolved", "removed"]
    body: str
    reply_count: int = 0
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="meta",
        serialization_alias="metadata",
    )
    moderation_history: list[Dict[str, Any]] = Field(
        default_factory=list,
        validation_alias="moderation_history",
        serialization_alias="moderation_history",
    )
    actor: GovernanceActorSummary | None = None
    created_at: datetime
    updated_at: datetime
    last_edited_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GovernanceDecisionTimelineEntry(BaseModel):
    # purpose: unify governance decisions, analytics, and overrides into one feed item schema
    # status: pilot

    entry_id: str
    entry_type: Literal[
        "override_recommendation",
        "override_action",
        "baseline_event",
        "analytics_snapshot",
        "coaching_note",
    ]
    occurred_at: datetime
    execution_id: UUID | None = None
    baseline_id: UUID | None = None
    rule_key: str | None = None
    action: str | None = None
    status: str | None = None
    summary: str | None = None
    detail: Dict[str, Any] = Field(default_factory=dict)
    actor: GovernanceActorSummary | None = None
    lineage: GovernanceOverrideLineageContext | None = None


class GovernanceDecisionTimelinePage(BaseModel):
    # purpose: paginated wrapper for governance decision timeline consumption
    # status: pilot

    entries: list[GovernanceDecisionTimelineEntry] = Field(default_factory=list)
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
        "escalated",
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
    stage_step_indexes: list[int] = Field(default_factory=list)
    stage_gate_keys: list[str] = Field(default_factory=list)
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
    published_snapshot_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ExecutionNarrativeWorkflowTemplateSnapshotOut(BaseModel):
    """Serialized governance template snapshot representation."""

    # purpose: expose immutable lifecycle snapshots for governance tooling
    # inputs: snapshot ORM rows
    # outputs: API-safe payload with serialized snapshot metadata
    # status: pilot
    id: UUID
    template_id: UUID
    template_key: str
    version: int
    status: str
    captured_at: datetime
    captured_by_id: UUID
    snapshot_payload: Dict[str, Any]

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
    workflow_template_snapshot_id: UUID | None = None
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
    guardrail_simulation: GovernanceGuardrailSimulationRecord | None = None
    guardrail_simulations: list[GovernanceGuardrailSimulationRecord] = Field(
        default_factory=list
    )
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
    workflow_template_snapshot_id: UUID | None = None
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


class CloningPlannerSequenceIn(BaseModel):
    """Cloning planner intake sequence descriptor."""

    # purpose: capture individual sequence uploads for planner intake requests
    name: str
    sequence: str
    metadata: dict[str, Any] | None = None


class CloningPlannerSessionCreate(BaseModel):
    """Payload for creating a cloning planner session."""

    # purpose: represent planner session creation inputs across API and tests
    assembly_strategy: str
    input_sequences: list[CloningPlannerSequenceIn]
    metadata: dict[str, Any] | None = None


class CloningPlannerStageRequest(BaseModel):
    """Payload for submitting stage outputs to the cloning planner."""

    # purpose: standardise stage updates including guardrail and task context
    payload: dict[str, Any]
    next_step: str | None = None
    status: str | None = None
    guardrail_state: dict[str, Any] | None = None
    task_id: str | None = None
    error: str | None = None


class CloningPlannerResumeRequest(BaseModel):
    """Resume payload for restarting cloning planner pipelines."""

    # purpose: capture restart instructions, optional overrides, and target step
    step: str | None = None
    overrides: dict[str, Any] | None = None


class CloningPlannerCancelRequest(BaseModel):
    """Cancellation payload for cloning planner sessions."""

    # purpose: record cancellation reasons for audit and guardrail context
    reason: str | None = None


class CloningPlannerFinalizeRequest(BaseModel):
    """Finalize payload for cloning planner sessions."""

    # purpose: capture optional guardrail payload when concluding planner workflows
    guardrail_state: dict[str, Any] | None = None


class CloningPlannerStageRecordOut(BaseModel):
    """Response schema for durable cloning planner stage records."""

    # purpose: expose checkpoint lineage, guardrail snapshots, and retry metadata
    id: UUID
    stage: str
    attempt: int
    retry_count: int
    status: str
    task_id: str | None = None
    payload_path: str | None = None
    payload_metadata: dict[str, Any]
    guardrail_snapshot: dict[str, Any]
    metrics: dict[str, Any]
    review_state: dict[str, Any]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CloningPlannerQCArtifactOut(BaseModel):
    """Response schema for QC artifacts stored for cloning planner sessions."""

    # purpose: surface chromatogram storage metadata, thresholds, and reviewer decisions
    id: UUID
    artifact_name: str | None = None
    sample_id: str | None = None
    trace_path: str | None = None
    storage_path: str | None = None
    metrics: dict[str, Any]
    thresholds: dict[str, Any]
    stage_record_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewer_decision: str | None = None
    reviewer_notes: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CloningPlannerSessionOut(BaseModel):
    """Response schema for cloning planner sessions."""

    # purpose: expose planner session state to API consumers and frontend wizard
    id: UUID
    created_by_id: UUID | None = None
    status: str
    assembly_strategy: str
    input_sequences: list[dict[str, Any]]
    primer_set: PrimerDesignResponse
    restriction_digest: RestrictionDigestResponse
    assembly_plan: AssemblySimulationResult
    qc_reports: QCReportResponse
    inventory_reservations: list[dict[str, Any]]
    guardrail_state: dict[str, Any]
    stage_timings: dict[str, Any]
    current_step: str | None = None
    celery_task_id: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    stage_history: list[CloningPlannerStageRecordOut]
    qc_artifacts: list[CloningPlannerQCArtifactOut]


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
