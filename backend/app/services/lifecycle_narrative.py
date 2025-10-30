"""Lifecycle narrative aggregation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas

# purpose: aggregate planner, custody, dna asset, and sharing workspace events into lifecycle timelines
# status: pilot
# depends_on: backend.app.models.CloningPlannerStageRecord, backend.app.models.GovernanceSampleCustodyLog
# related_docs: docs/lifecycle/overview.md


@dataclass(frozen=True)
class _EventAccumulator:
    entries: list[schemas.LifecycleTimelineEntry]

    def append(
        self,
        *,
        entry_id: str,
        source: str,
        event_type: str,
        occurred_at: datetime,
        title: str,
        summary: str | None,
        metadata: dict[str, object],
    ) -> None:
        self.entries.append(
            schemas.LifecycleTimelineEntry(
                entry_id=entry_id,
                source=source,
                event_type=event_type,
                occurred_at=occurred_at,
                title=title,
                summary=summary,
                metadata=metadata,
            )
        )


def build_lifecycle_timeline(
    db: Session,
    scope: schemas.LifecycleScope,
    *,
    limit: int = 250,
) -> schemas.LifecycleTimelineResponse:
    """Assemble lifecycle timeline entries and risk summary for the provided scope."""

    entries: list[schemas.LifecycleTimelineEntry] = []
    collector = _EventAccumulator(entries)

    if scope.planner_session_id:
        _collect_planner_history(db, collector, scope.planner_session_id, limit=limit)
    if scope.dna_asset_id or scope.dna_asset_version_id:
        _collect_dna_guardrail_events(db, collector, scope, limit=limit)
    if (
        scope.custody_log_inventory_item_id
        or scope.planner_session_id
        or scope.protocol_execution_id
    ):
        _collect_custody_logs(db, collector, scope, limit=limit)
    if scope.repository_id:
        _collect_repository_timeline(db, collector, scope.repository_id, limit=limit)

    entries.sort(key=lambda entry: entry.occurred_at)
    summary = _build_summary(db, scope, entries)
    summary.context_chips = _build_context_chips(scope)
    return schemas.LifecycleTimelineResponse(scope=scope, summary=summary, entries=entries)


def _collect_planner_history(
    db: Session,
    collector: _EventAccumulator,
    session_id: UUID,
    *,
    limit: int,
) -> None:
    records: Sequence[models.CloningPlannerStageRecord] = (
        db.query(models.CloningPlannerStageRecord)
        .filter(models.CloningPlannerStageRecord.session_id == session_id)
        .order_by(models.CloningPlannerStageRecord.created_at.asc())
        .limit(limit)
        .all()
    )
    for record in records:
        occurred_at = record.completed_at or record.updated_at or record.created_at
        guardrail = record.guardrail_snapshot or {}
        guardrail_flags = guardrail.get("flags") or guardrail.get("reasons") or []
        metadata = {
            "stage": record.stage,
            "status": record.status,
            "checkpoint_key": record.checkpoint_key,
            "guardrail_flags": guardrail_flags,
            "resume_token": record.checkpoint_payload.get("resume_token")
            if isinstance(record.checkpoint_payload, dict)
            else None,
        }
        collector.append(
            entry_id=f"planner:{record.id}",
            source="planner",
            event_type=f"planner.{record.stage}.{record.status}",
            occurred_at=occurred_at or datetime.now(timezone.utc),
            title=f"{record.stage.title()} · {record.status}",
            summary=record.guardrail_transition.get("summary")
            if isinstance(record.guardrail_transition, dict)
            else None,
            metadata=metadata,
        )


def _collect_dna_guardrail_events(
    db: Session,
    collector: _EventAccumulator,
    scope: schemas.LifecycleScope,
    *,
    limit: int,
) -> None:
    query = db.query(models.DNAAssetGuardrailEvent)
    if scope.dna_asset_version_id:
        query = query.filter(
            models.DNAAssetGuardrailEvent.version_id == scope.dna_asset_version_id
        )
    elif scope.dna_asset_id:
        query = query.filter(models.DNAAssetGuardrailEvent.asset_id == scope.dna_asset_id)
    events = (
        query.options(joinedload(models.DNAAssetGuardrailEvent.version))
        .order_by(models.DNAAssetGuardrailEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    for event in events:
        metadata = {
            "asset_id": str(event.asset_id),
            "version_id": str(event.version_id) if event.version_id else None,
            "details": event.details or {},
        }
        summary = None
        if event.details:
            summary = event.details.get("summary") or event.details.get("message")
        collector.append(
            entry_id=f"dna:{event.id}",
            source="dna_asset",
            event_type=event.event_type,
            occurred_at=event.created_at,
            title=f"DNA guardrail · {event.event_type}",
            summary=summary,
            metadata=metadata,
        )


def _collect_custody_logs(
    db: Session,
    collector: _EventAccumulator,
    scope: schemas.LifecycleScope,
    *,
    limit: int,
) -> None:
    query = db.query(models.GovernanceSampleCustodyLog)
    if scope.planner_session_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.planner_session_id == scope.planner_session_id
        )
    if scope.protocol_execution_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.protocol_execution_id
            == scope.protocol_execution_id
        )
    if scope.custody_log_inventory_item_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.inventory_item_id
            == scope.custody_log_inventory_item_id
        )
    if scope.dna_asset_version_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.asset_version_id
            == scope.dna_asset_version_id
        )
    elif scope.dna_asset_id:
        query = query.filter(
            sa.or_(
                models.GovernanceSampleCustodyLog.asset_version_id.is_(None),
                models.GovernanceSampleCustodyLog.asset_version.has(
                    models.DNAAssetVersion.asset_id == scope.dna_asset_id
                ),
            )
        )
    logs = (
        query.options(
            joinedload(models.GovernanceSampleCustodyLog.compartment).joinedload(
                models.GovernanceFreezerCompartment.freezer
            ),
            joinedload(models.GovernanceSampleCustodyLog.inventory_item),
        )
        .order_by(models.GovernanceSampleCustodyLog.performed_at.asc())
        .limit(limit)
        .all()
    )
    for log in logs:
        freezer = log.compartment.freezer.name if log.compartment and log.compartment.freezer else None
        metadata = {
            "compartment": log.compartment.label if log.compartment else None,
            "freezer": freezer,
            "inventory_item_id": str(log.inventory_item_id)
            if log.inventory_item_id
            else None,
            "guardrail_flags": log.guardrail_flags,
            "quantity": log.quantity,
            "notes": log.notes,
        }
        summary_parts: list[str] = []
        if log.quantity is not None and log.quantity_units:
            summary_parts.append(f"{log.quantity} {log.quantity_units}")
        if log.guardrail_flags:
            summary_parts.append(
                ", ".join(sorted(log.guardrail_flags))
            )
        summary = " · ".join(summary_parts) if summary_parts else None
        collector.append(
            entry_id=f"custody:{log.id}",
            source="custody",
            event_type=f"custody.{log.custody_action}",
            occurred_at=log.performed_at,
            title=f"Custody · {log.custody_action}",
            summary=summary,
            metadata=metadata,
        )


def _collect_repository_timeline(
    db: Session,
    collector: _EventAccumulator,
    repository_id: UUID,
    *,
    limit: int,
) -> None:
    events: Iterable[models.DNARepositoryTimelineEvent] = (
        db.query(models.DNARepositoryTimelineEvent)
        .filter(models.DNARepositoryTimelineEvent.repository_id == repository_id)
        .order_by(models.DNARepositoryTimelineEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    for event in events:
        metadata = {
            "release_id": str(event.release_id) if event.release_id else None,
            "payload": event.payload or {},
        }
        summary = None
        if event.payload:
            summary = event.payload.get("summary") or event.payload.get("message")
        collector.append(
            entry_id=f"repository:{event.id}",
            source="repository",
            event_type=event.event_type,
            occurred_at=event.created_at,
            title=f"Repository · {event.event_type}",
            summary=summary,
            metadata=metadata,
        )


def _build_summary(
    db: Session,
    scope: schemas.LifecycleScope,
    entries: Sequence[schemas.LifecycleTimelineEntry],
) -> schemas.LifecycleSummary:
    open_escalations = _count_open_escalations(db, scope)
    active_guardrails = sum(
        1
        for entry in entries
        if entry.metadata.get("guardrail_flags")
        and len(entry.metadata["guardrail_flags"]) > 0
    )
    latest = entries[-1].occurred_at if entries else None
    custody_state = None
    compliance_allowed: bool | None = None
    compliance_flags: list[str] = []
    compliance_region: str | None = None
    if scope.custody_log_inventory_item_id:
        item = db.get(models.InventoryItem, scope.custody_log_inventory_item_id)
        if item:
            custody_state = item.custody_state
    if scope.planner_session_id:
        planner = db.get(models.CloningPlannerSession, scope.planner_session_id)
        if planner and isinstance(planner.guardrail_state, dict):
            compliance_state = planner.guardrail_state.get("compliance")
            if isinstance(compliance_state, dict):
                if compliance_state.get("allowed") is not None:
                    compliance_allowed = bool(compliance_state.get("allowed"))
                region = compliance_state.get("effective_region") or compliance_state.get("region")
                if region:
                    compliance_region = str(region)
                flags = compliance_state.get("flags")
                if isinstance(flags, list):
                    for flag in flags:
                        value = str(flag)
                        if value not in compliance_flags:
                            compliance_flags.append(value)
    asset: models.DNAAsset | None = None
    if scope.dna_asset_version_id:
        version = db.get(models.DNAAssetVersion, scope.dna_asset_version_id)
        if version:
            asset = db.get(models.DNAAsset, version.asset_id)
    elif scope.dna_asset_id:
        asset = db.get(models.DNAAsset, scope.dna_asset_id)
    if asset and isinstance(asset.meta, dict):
        compliance_meta = asset.meta.get("compliance")
        if isinstance(compliance_meta, dict):
            if compliance_meta.get("allowed") is not None:
                compliance_allowed = bool(compliance_meta.get("allowed"))
            region = compliance_meta.get("effective_region") or compliance_meta.get("region")
            if region:
                compliance_region = str(region)
            flags = compliance_meta.get("flags")
            if isinstance(flags, list):
                for flag in flags:
                    value = str(flag)
                    if value not in compliance_flags:
                        compliance_flags.append(value)
    return schemas.LifecycleSummary(
        total_events=len(entries),
        open_escalations=open_escalations,
        active_guardrails=active_guardrails,
        latest_event_at=latest,
        custody_state=custody_state,
        context_chips=[],
        compliance_allowed=compliance_allowed,
        compliance_flags=compliance_flags,
        compliance_region=compliance_region,
    )


def _count_open_escalations(db: Session, scope: schemas.LifecycleScope) -> int:
    query = db.query(sa.func.count(models.GovernanceCustodyEscalation.id))
    query = query.filter(
        models.GovernanceCustodyEscalation.status.in_(["open", "acknowledged"])
    )
    joined_logs = False
    if scope.protocol_execution_id:
        query = query.filter(
            models.GovernanceCustodyEscalation.protocol_execution_id
            == scope.protocol_execution_id
        )
    if scope.custody_log_inventory_item_id:
        query = query.join(models.GovernanceSampleCustodyLog)
        joined_logs = True
        query = query.filter(
            models.GovernanceSampleCustodyLog.inventory_item_id
            == scope.custody_log_inventory_item_id
        )
    if scope.planner_session_id:
        if not joined_logs:
            query = query.join(models.GovernanceSampleCustodyLog)
            joined_logs = True
        query = query.filter(
            models.GovernanceSampleCustodyLog.planner_session_id
            == scope.planner_session_id
        )
    if scope.dna_asset_version_id:
        query = query.filter(
            models.GovernanceCustodyEscalation.asset_version_id
            == scope.dna_asset_version_id
        )
    elif scope.dna_asset_id:
        query = query.outerjoin(models.DNAAssetVersion).filter(
            sa.or_(
                models.DNAAssetVersion.asset_id == scope.dna_asset_id,
                models.GovernanceCustodyEscalation.asset_version_id.is_(None),
            )
        )
    return int(query.scalar() or 0)


def _build_context_chips(scope: schemas.LifecycleScope) -> list[schemas.LifecycleContextChip]:
    chips: list[schemas.LifecycleContextChip] = []
    if scope.planner_session_id:
        chips.append(
            schemas.LifecycleContextChip(
                label="Planner session",
                value=str(scope.planner_session_id),
                href=f"/planner/{scope.planner_session_id}",
                tone="primary",
            )
        )
    if scope.dna_asset_id:
        chips.append(
            schemas.LifecycleContextChip(
                label="DNA asset",
                value=str(scope.dna_asset_id),
                href=f"/dna-viewer/{scope.dna_asset_id}",
                tone="governance",
            )
        )
    if scope.repository_id:
        chips.append(
            schemas.LifecycleContextChip(
                label="Repository",
                value=str(scope.repository_id),
                href=f"/sharing/{scope.repository_id}",
                tone="neutral",
            )
        )
    if scope.custody_log_inventory_item_id:
        chips.append(
            schemas.LifecycleContextChip(
                label="Sample",
                value=str(scope.custody_log_inventory_item_id),
                href=f"/samples/{scope.custody_log_inventory_item_id}",
                tone="warning",
            )
        )
    if scope.protocol_execution_id:
        chips.append(
            schemas.LifecycleContextChip(
                label="Protocol execution",
                value=str(scope.protocol_execution_id),
                href=f"/experiment-console/executions/{scope.protocol_execution_id}",
                tone="info",
            )
        )
    return chips
