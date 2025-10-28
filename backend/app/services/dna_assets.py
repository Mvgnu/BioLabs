"""DNA asset lifecycle service helpers."""

# purpose: provide persistence, diffing, and governance hooks for DNA asset workflows
# status: experimental
# depends_on: backend.app.models, backend.app.schemas.dna_assets, backend.app.services.sequence_toolkit
# related_docs: docs/dna_assets.md

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..schemas import (
    DNAAnnotationOut,
    DNAAnnotationPayload,
    DNAAssetCreate,
    DNAAssetDiffResponse,
    DNAAssetGovernanceUpdate,
    DNAAssetGuardrailEventOut,
    DNAAssetSummary,
    DNAAssetVersionCreate,
    DNAAssetVersionOut,
    SequenceToolkitProfile,
)
from . import sequence_toolkit

_DEFAULT_PROFILE = SequenceToolkitProfile()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_annotations(
    annotations: Iterable[DNAAnnotationPayload] | None,
) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for annotation in annotations or []:
        payload = annotation.model_dump(mode="python")
        payload.setdefault("qualifiers", {})
        normalised.append(payload)
    return normalised


def _apply_tags(asset: models.DNAAsset, tags: Sequence[str]) -> None:
    existing = {tag.tag for tag in asset.tags_rel}
    now = _utcnow()
    for tag in tags:
        value = tag.strip()
        if not value or value in existing:
            continue
        asset.tags_rel.append(
            models.DNAAssetTag(asset_id=asset.id, tag=value, created_at=now)
        )


def _sequence_checksum(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("utf-8")).hexdigest()


def _build_version(
    asset: models.DNAAsset,
    payload: DNAAssetVersionCreate | DNAAssetCreate,
    *,
    created_by_id: UUID | None,
    profile: SequenceToolkitProfile,
) -> models.DNAAssetVersion:
    metrics = sequence_toolkit.compute_sequence_metrics(payload.sequence)
    version_index = len(asset.versions) + 1
    version = models.DNAAssetVersion(
        asset_id=asset.id,
        version_index=version_index,
        sequence=payload.sequence,
        sequence_checksum=_sequence_checksum(payload.sequence),
        sequence_length=metrics["length"],
        gc_content=metrics["gc_content"],
        meta=dict(payload.metadata or {}),
        comment=getattr(payload, "comment", None),
        created_at=_utcnow(),
        created_by_id=created_by_id,
    )
    annotations = _normalise_annotations(getattr(payload, "annotations", None))
    for descriptor in annotations:
        version.annotations.append(
            models.DNAAssetAnnotation(
                label=descriptor.get("label", "feature"),
                feature_type=descriptor.get("feature_type") or descriptor.get("type", "feature"),
                start=int(descriptor.get("start", 0)),
                end=int(descriptor.get("end", 0)),
                strand=descriptor.get("strand"),
                qualifiers=dict(descriptor.get("qualifiers") or {}),
            )
        )
    return version


def create_asset(
    db: Session,
    *,
    payload: DNAAssetCreate,
    created_by: models.User | None,
    profile: SequenceToolkitProfile | None = None,
) -> models.DNAAsset:
    """Create a DNA asset and seed the initial version."""

    profile = profile or _DEFAULT_PROFILE
    now = _utcnow()
    asset = models.DNAAsset(
        name=payload.name,
        status="draft",
        team_id=payload.team_id,
        created_by_id=getattr(created_by, "id", None),
        created_at=now,
        updated_at=now,
        meta=dict(payload.metadata or {}),
    )
    db.add(asset)
    db.flush()
    version = _build_version(
        asset,
        payload,
        created_by_id=asset.created_by_id,
        profile=profile,
    )
    asset.versions.append(version)
    asset.latest_version = version
    _apply_tags(asset, payload.tags)
    db.flush()
    return asset


def add_version(
    db: Session,
    *,
    asset: models.DNAAsset,
    payload: DNAAssetVersionCreate,
    created_by: models.User | None,
    profile: SequenceToolkitProfile | None = None,
) -> models.DNAAssetVersion:
    """Append a new version to a DNA asset and refresh metadata."""

    profile = profile or _DEFAULT_PROFILE
    version = _build_version(
        asset,
        payload,
        created_by_id=getattr(created_by, "id", None),
        profile=profile,
    )
    asset.versions.append(version)
    asset.latest_version = version
    asset.updated_at = _utcnow()
    if payload.metadata:
        asset.meta.update(payload.metadata)
    db.flush()
    return version


def record_guardrail_event(
    db: Session,
    *,
    asset: models.DNAAsset,
    version: models.DNAAssetVersion | None,
    event: DNAAssetGovernanceUpdate,
    created_by: models.User | None,
) -> models.DNAAssetGuardrailEvent:
    """Persist a guardrail event for governance dashboards."""

    record = models.DNAAssetGuardrailEvent(
        asset_id=asset.id,
        version_id=version.id if version else None,
        event_type=event.event_type,
        details=dict(event.details or {}),
        created_at=_utcnow(),
        created_by_id=getattr(created_by, "id", None),
    )
    db.add(record)
    asset.updated_at = _utcnow()
    db.flush()
    return record


def serialize_version(version: models.DNAAssetVersion) -> DNAAssetVersionOut:
    """Convert a version ORM object into an API schema."""

    annotations = [
        DNAAnnotationOut(
            id=annotation.id,
            label=annotation.label,
            feature_type=annotation.feature_type,
            start=annotation.start,
            end=annotation.end,
            strand=annotation.strand,
            qualifiers=annotation.qualifiers or {},
        )
        for annotation in version.annotations
    ]
    return DNAAssetVersionOut(
        id=version.id,
        version_index=version.version_index,
        sequence_length=version.sequence_length,
        gc_content=version.gc_content,
        created_at=version.created_at,
        created_by_id=version.created_by_id,
        metadata=version.meta or {},
        annotations=annotations,
    )


def serialize_asset(asset: models.DNAAsset) -> DNAAssetSummary:
    """Serialize a DNA asset with its latest version."""

    latest = asset.latest_version
    latest_serialized = serialize_version(latest) if latest else None
    return DNAAssetSummary(
        id=asset.id,
        name=asset.name,
        status=asset.status,
        team_id=asset.team_id,
        created_by_id=asset.created_by_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        tags=sorted(tag.tag for tag in asset.tags_rel),
        latest_version=latest_serialized,
    )


def serialize_guardrail_event(
    event: models.DNAAssetGuardrailEvent,
) -> DNAAssetGuardrailEventOut:
    return DNAAssetGuardrailEventOut(
        id=event.id,
        asset_id=event.asset_id,
        version_id=event.version_id,
        event_type=event.event_type,
        created_at=event.created_at,
        created_by_id=event.created_by_id,
        details=event.details or {},
    )


def get_asset(db: Session, asset_id: UUID) -> models.DNAAsset | None:
    return db.get(models.DNAAsset, asset_id)


def list_assets(
    db: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 50,
) -> list[models.DNAAsset]:
    stmt = select(models.DNAAsset)
    if team_id:
        stmt = stmt.where(models.DNAAsset.team_id == team_id)
    stmt = stmt.order_by(models.DNAAsset.updated_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def diff_versions(
    version_a: models.DNAAssetVersion,
    version_b: models.DNAAssetVersion,
) -> DNAAssetDiffResponse:
    metrics_a = {
        "length": version_a.sequence_length,
        "gc_content": version_a.gc_content,
    }
    metrics_b = {
        "length": version_b.sequence_length,
        "gc_content": version_b.gc_content,
    }
    diff = sequence_toolkit.diff_sequences(version_a.sequence, version_b.sequence)
    return DNAAssetDiffResponse(
        from_version=serialize_version(version_a),
        to_version=serialize_version(version_b),
        substitutions=diff["substitutions"],
        insertions=diff["insertions"],
        deletions=diff["deletions"],
        gc_delta=metrics_b["gc_content"] - metrics_a["gc_content"],
    )

