"""Lifecycle narrative aggregation schemas."""

# purpose: define request and response models for lifecycle narrative aggregation
# status: experimental

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LifecycleScope(BaseModel):
    """Selector describing which artefacts to aggregate into a lifecycle timeline."""

    planner_session_id: UUID | None = None
    dna_asset_id: UUID | None = None
    dna_asset_version_id: UUID | None = None
    custody_log_inventory_item_id: UUID | None = None
    protocol_execution_id: UUID | None = None
    repository_id: UUID | None = None


class LifecycleContextChip(BaseModel):
    """UI context chip describing related artefacts or governance posture."""

    label: str
    value: str
    kind: str = Field(default="default")


class LifecycleTimelineEntry(BaseModel):
    """Single lifecycle event entry emitted by the aggregation service."""

    entry_id: str
    source: str
    event_type: str
    occurred_at: datetime
    title: str
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifecycleSummary(BaseModel):
    """Aggregated summary for quick status rendering."""

    total_events: int = 0
    open_escalations: int = 0
    active_guardrails: int = 0
    latest_event_at: datetime | None = None
    custody_state: str | None = None
    context_chips: list[LifecycleContextChip] = Field(default_factory=list)


class LifecycleTimelineResponse(BaseModel):
    """Response payload produced by the lifecycle aggregation endpoint."""

    scope: LifecycleScope
    summary: LifecycleSummary
    entries: list[LifecycleTimelineEntry] = Field(default_factory=list)

