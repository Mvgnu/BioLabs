"""Schemas for DNA asset lifecycle APIs."""

# purpose: define request/response contracts for DNA asset persistence and governance workflows
# status: experimental
# related_docs: docs/dna_assets.md

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DNAAnnotationSegment(BaseModel):
    """Segment for annotations spanning multiple intervals."""

    # purpose: represent joined CDS/regulatory spans for viewer overlays
    start: int
    end: int
    strand: Optional[int] = None


class DNAAnnotationPayload(BaseModel):
    """Annotation descriptor used during ingestion and serialization."""

    # purpose: represent feature annotations with positional metadata
    label: str
    feature_type: str = Field(default="feature", alias="type")
    start: int
    end: int
    strand: Optional[int] = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    segments: List[DNAAnnotationSegment] = Field(default_factory=list)
    provenance_tags: List[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
    }


class DNAAssetCreate(BaseModel):
    """Payload for creating a DNA asset with an initial version."""

    # purpose: capture minimal information for DNA asset ingestion flows
    name: str
    sequence: str
    team_id: Optional[UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    annotations: List[DNAAnnotationPayload] = Field(default_factory=list)


class DNAAssetVersionCreate(BaseModel):
    """Payload for registering an additional DNA asset version."""

    # purpose: support incremental updates while maintaining annotation history
    sequence: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    annotations: List[DNAAnnotationPayload] = Field(default_factory=list)
    comment: Optional[str] = None


class DNAAnnotationOut(DNAAnnotationPayload):
    """Serialized annotation with identifier."""

    id: UUID


class DNAAssetKineticsSummary(BaseModel):
    """Aggregated kinetics descriptors for DNA asset versions."""

    # purpose: expose enzyme, buffer, and ligation tags surfaced by toolkit analyses
    enzymes: List[str] = Field(default_factory=list)
    buffers: List[str] = Field(default_factory=list)
    ligation_profiles: List[str] = Field(default_factory=list)
    metadata_tags: List[str] = Field(default_factory=list)


class DNAAssetGuardrailHeuristics(BaseModel):
    """Guardrail heuristics derived from toolkit simulations."""

    # purpose: align DNA asset views with planner guardrail summaries
    primers: dict[str, Any] = Field(default_factory=dict)
    restriction: dict[str, Any] = Field(default_factory=dict)
    assembly: dict[str, Any] = Field(default_factory=dict)


class DNAAssetVersionOut(BaseModel):
    """Serialized view of a DNA asset version."""

    id: UUID
    version_index: int
    sequence_length: int
    gc_content: float
    created_at: datetime
    created_by_id: Optional[UUID]
    metadata: dict[str, Any]
    annotations: List[DNAAnnotationOut]
    kinetics_summary: DNAAssetKineticsSummary = Field(default_factory=DNAAssetKineticsSummary)
    assembly_presets: List[str] = Field(default_factory=list)
    guardrail_heuristics: DNAAssetGuardrailHeuristics = Field(default_factory=DNAAssetGuardrailHeuristics)
    toolkit_recommendations: dict[str, Any] = Field(default_factory=dict)


class DNAAssetSummary(BaseModel):
    """High-level DNA asset view with latest version summary."""

    id: UUID
    name: str
    status: str
    team_id: Optional[UUID]
    created_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    meta: dict[str, Any] = Field(default_factory=dict)
    latest_version: Optional[DNAAssetVersionOut] = None


class DNAAssetDiffResponse(BaseModel):
    """Diff summary for two DNA asset versions."""

    from_version: DNAAssetVersionOut
    to_version: DNAAssetVersionOut
    substitutions: int
    insertions: int
    deletions: int
    gc_delta: float


class DNAAssetGuardrailEventOut(BaseModel):
    """Governance event associated with a DNA asset version."""

    id: UUID
    asset_id: UUID
    version_id: Optional[UUID]
    event_type: str
    created_at: datetime
    created_by_id: Optional[UUID]
    details: dict[str, Any]


class DNAAssetGovernanceUpdate(BaseModel):
    """Payload for recording guardrail transitions."""

    event_type: str
    details: dict[str, Any] = Field(default_factory=dict)


class DNAViewerFeature(BaseModel):
    """Feature element displayed within viewer tracks."""

    # purpose: provide viewer-ready annotation descriptors with guardrail badges
    label: str
    feature_type: str
    start: int
    end: int
    strand: Optional[int] = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    guardrail_badges: List[str] = Field(default_factory=list)
    segments: List[DNAAnnotationSegment] = Field(default_factory=list)
    provenance_tags: List[str] = Field(default_factory=list)


class DNAViewerAnalytics(BaseModel):
    """Aggregated analytics used for viewer overlays."""

    # purpose: supply scientists with codon, GC, and thermodynamic overlays
    codon_usage: dict[str, float] = Field(default_factory=dict)
    gc_skew: List[float] = Field(default_factory=list)
    thermodynamic_risk: dict[str, Any] = Field(default_factory=dict)
    translation_frames: dict[str, Any] = Field(default_factory=dict)
    codon_adaptation_index: float = 0.0
    motif_hotspots: List[dict[str, Any]] = Field(default_factory=list)


class DNAViewerTrack(BaseModel):
    """Logical grouping of viewer features."""

    # purpose: cluster annotations into viewer tracks (e.g., features, guardrails)
    name: str
    features: List[DNAViewerFeature] = Field(default_factory=list)


class DNAViewerGuardrailTimelineEvent(BaseModel):
    """Serialized guardrail event for viewer governance overlays."""

    # purpose: surface governance guardrail events in viewer payloads
    id: UUID
    event_type: str
    severity: Optional[str] = None
    created_at: datetime
    created_by_id: Optional[UUID]
    details: dict[str, Any] = Field(default_factory=dict)


class DNAViewerCustodyLedgerEntry(BaseModel):
    """Custody ledger snapshot aligned with viewer governance overlays."""

    # purpose: expose custody actions with guardrail annotations for DNA viewer narratives
    id: UUID
    performed_at: datetime
    custody_action: str
    quantity: Optional[int] = None
    quantity_units: Optional[str] = None
    compartment_label: Optional[str] = None
    guardrail_flags: List[str] = Field(default_factory=list)
    planner_session_id: Optional[UUID] = None
    branch_id: Optional[str] = None
    performed_by_id: Optional[UUID] = None
    performed_for_team_id: Optional[UUID] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DNAViewerCustodyEscalation(BaseModel):
    """Active custody escalation surfaced for DNA viewer guardrail context."""

    # purpose: communicate custody escalations linked to the DNA asset lineage
    id: UUID
    severity: str
    status: str
    reason: str
    created_at: datetime
    due_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    assigned_to_id: Optional[UUID] = None
    planner_session_id: Optional[UUID] = None
    asset_version_id: Optional[UUID] = None
    guardrail_flags: List[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DNAViewerGovernanceTimelineEntry(BaseModel):
    """Unified governance timeline entry for DNA viewer overlays."""

    # purpose: stitch guardrail, custody, and planner checkpoints into viewer narratives
    id: str
    timestamp: datetime
    source: str
    title: str
    severity: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class DNAViewerLineageBreadcrumb(BaseModel):
    """Lightweight lineage descriptor for DNA asset versions."""

    # purpose: provide provenance breadcrumbs for governance dashboards
    version_id: UUID
    version_index: int
    created_at: datetime
    created_by_id: Optional[UUID]
    sequence_length: int
    comment: Optional[str] = None


class DNAViewerPlannerContext(BaseModel):
    """Planner checkpoint summary aligned with DNA viewer governance overlays."""

    # purpose: expose planner branch and recovery state linked to DNA assets
    session_id: UUID
    status: str
    guardrail_gate: Optional[str] = None
    custody_status: Optional[str] = None
    active_branch_id: Optional[str] = None
    branch_order: List[str] = Field(default_factory=list)
    replay_window: dict[str, Any] = Field(default_factory=dict)
    recovery_context: dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class DNAViewerGovernanceContext(BaseModel):
    """Governance-centric overlays emitted with viewer payloads."""

    # purpose: bundle guardrail history, lineage breadcrumbs, and risk metrics
    lineage: List[DNAViewerLineageBreadcrumb] = Field(default_factory=list)
    guardrail_history: List[DNAViewerGuardrailTimelineEvent] = Field(default_factory=list)
    regulatory_feature_density: Optional[float] = None
    mitigation_playbooks: List[str] = Field(default_factory=list)
    custody_ledger: List[DNAViewerCustodyLedgerEntry] = Field(default_factory=list)
    custody_escalations: List[DNAViewerCustodyEscalation] = Field(default_factory=list)
    timeline: List[DNAViewerGovernanceTimelineEntry] = Field(default_factory=list)
    planner_sessions: List[DNAViewerPlannerContext] = Field(default_factory=list)
    sop_links: List[str] = Field(default_factory=list)


class DNAViewerTranslation(BaseModel):
    """Translated reading frame snippet for viewer overlays."""

    # purpose: surface amino acid translations for CDS annotations
    label: str
    frame: int
    sequence: str
    amino_acids: str


class DNAViewerPayload(BaseModel):
    """Viewer-ready payload bundling tracks, guardrails, and kinetics."""

    # purpose: transmit DNA asset viewer state to frontend components
    asset: DNAAssetSummary
    version: DNAAssetVersionOut
    sequence: str
    topology: str
    tracks: List[DNAViewerTrack]
    translations: List[DNAViewerTranslation] = Field(default_factory=list)
    kinetics_summary: DNAAssetKineticsSummary
    guardrails: DNAAssetGuardrailHeuristics
    analytics: DNAViewerAnalytics
    diff: Optional[DNAAssetDiffResponse] = None
    governance_context: DNAViewerGovernanceContext = Field(default_factory=DNAViewerGovernanceContext)
    toolkit_recommendations: dict[str, Any] = Field(default_factory=dict)

