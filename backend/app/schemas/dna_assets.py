"""Schemas for DNA asset lifecycle APIs."""

# purpose: define request/response contracts for DNA asset persistence and governance workflows
# status: experimental
# related_docs: docs/dna_assets.md

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DNAAnnotationPayload(BaseModel):
    """Annotation descriptor used during ingestion and serialization."""

    # purpose: represent feature annotations with positional metadata
    label: str
    feature_type: str = Field(default="feature", alias="type")
    start: int
    end: int
    strand: Optional[int] = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)

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

