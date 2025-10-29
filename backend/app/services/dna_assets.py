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
    DNAAssetGuardrailHeuristics,
    DNAAssetKineticsSummary,
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


def _primer_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise primer metrics for DNA asset guardrails."""

    # purpose: share planner-aligned primer heuristics with asset serialization
    primers = [p for p in result.get("primers", []) if p.get("status") == "ok"]
    warning_count = sum(len(p.get("warnings", [])) for p in primers)
    tm_values = [
        p.get("forward", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("forward")
    ] + [
        p.get("reverse", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("reverse")
    ]
    tm_values = [value for value in tm_values if isinstance(value, (int, float))]
    tm_span = max(tm_values) - min(tm_values) if tm_values else 0.0
    metadata_tags = sorted({
        tag
        for primer in primers
        for tag in primer.get("metadata_tags", [])
    })
    return {
        "primer_sets": len(primers),
        "primer_warnings": warning_count,
        "primer_state": "review" if warning_count else "ok",
        "metadata_tags": metadata_tags,
        "tm_span": tm_span,
    }


def _restriction_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise restriction digest guardrail metadata."""

    # purpose: propagate kinetics, buffer, and tag details to asset views
    alerts = result.get("alerts", [])
    digests = result.get("digests", [])
    metadata_tags = sorted({
        tag
        for digest in digests
        for tag in digest.get("metadata_tags", [])
    })
    buffers = sorted({
        (digest.get("buffer") or {}).get("name")
        for digest in digests
        if (digest.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for digest in digests
        for profile in digest.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "restriction_alerts": alerts,
        "restriction_state": "review" if alerts else "ok",
        "metadata_tags": metadata_tags,
        "buffers": buffers,
        "kinetics": kinetics,
    }


def _assembly_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise assembly simulation outputs for guardrails."""

    # purpose: align asset summaries with planner assembly heuristics
    success = result.get("average_success", 0.0)
    state = "ok" if success >= 0.7 else "review"
    steps = result.get("steps", [])
    metadata_tags = sorted({
        tag
        for step in steps
        for tag in step.get("metadata_tags", [])
    })
    ligation_profiles = sorted({
        (step.get("ligation_profile") or {}).get("strategy")
        for step in steps
        if (step.get("ligation_profile") or {}).get("strategy")
    })
    buffers = sorted({
        (step.get("buffer") or {}).get("name")
        for step in steps
        if (step.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for step in steps
        for profile in step.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "assembly_success": success,
        "assembly_state": state,
        "metadata_tags": metadata_tags,
        "ligation_profiles": ligation_profiles,
        "buffers": buffers,
        "kinetics": kinetics,
    }


def _kinetics_summary(digest: dict[str, Any], assembly: dict[str, Any]) -> dict[str, Any]:
    """Aggregate kinetics descriptors across digest and assembly outputs."""

    # purpose: provide reusable kinetics summaries for DNA asset serialization
    enzymes: set[str] = set()
    buffers: set[str] = set()
    ligation_profiles: set[str] = set()
    metadata_tags: set[str] = set()
    for entry in digest.get("digests", []):
        metadata_tags.update(entry.get("metadata_tags", []))
        buffer = (entry.get("buffer") or {}).get("name")
        if buffer:
            buffers.add(buffer)
        for profile in entry.get("kinetics_profiles", []):
            if profile.get("name"):
                enzymes.add(profile["name"])
            metadata_tags.update(profile.get("metadata_tags", []))
    for step in assembly.get("steps", []):
        metadata_tags.update(step.get("metadata_tags", []))
        buffer = (step.get("buffer") or {}).get("name")
        if buffer:
            buffers.add(buffer)
        ligation = step.get("ligation_profile") or {}
        strategy = ligation.get("strategy")
        if strategy:
            ligation_profiles.add(strategy)
        for profile in step.get("kinetics_profiles", []):
            if profile.get("name"):
                enzymes.add(profile["name"])
            metadata_tags.update(profile.get("metadata_tags", []))
    return {
        "enzymes": sorted(enzymes),
        "buffers": sorted(buffers),
        "ligation_profiles": sorted(ligation_profiles),
        "metadata_tags": sorted(metadata_tags),
    }


def _analyse_sequence_guardrails(sequence: str, profile: SequenceToolkitProfile) -> dict[str, Any]:
    """Run toolkit analyses to derive guardrail and kinetics summaries."""

    # purpose: ensure DNA asset serialization reflects kinetics-aware toolkit outputs
    template = [{"name": "asset_version", "sequence": sequence}]
    primer_payload = sequence_toolkit.design_primers(template, config=profile)
    digest_payload = sequence_toolkit.analyze_restriction_digest(template, config=profile)
    assembly_payload = sequence_toolkit.simulate_assembly(
        primer_payload,
        digest_payload,
        config=profile,
        strategy=profile.assembly.strategy,
    )
    guardrails = {
        "primers": _primer_guardrail_summary(primer_payload),
        "restriction": _restriction_guardrail_summary(digest_payload),
        "assembly": _assembly_guardrail_summary(assembly_payload),
    }
    kinetics = _kinetics_summary(digest_payload, assembly_payload)
    presets: set[str] = {profile.assembly.strategy}
    for step in assembly_payload.get("steps", []):
        strategy = step.get("strategy")
        if strategy:
            presets.add(strategy)
        ligation = step.get("ligation_profile") or {}
        ligation_strategy = ligation.get("strategy")
        if ligation_strategy:
            presets.add(ligation_strategy)
    return {
        "guardrails": guardrails,
        "kinetics": kinetics,
        "assembly_presets": sorted(presets),
    }


def _primer_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise primer metrics for DNA asset guardrails."""

    # purpose: share planner-aligned primer heuristics with asset serialization
    primers = [p for p in result.get("primers", []) if p.get("status") == "ok"]
    warning_count = sum(len(p.get("warnings", [])) for p in primers)
    tm_values = [
        p.get("forward", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("forward")
    ] + [
        p.get("reverse", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("reverse")
    ]
    tm_values = [value for value in tm_values if isinstance(value, (int, float))]
    tm_span = max(tm_values) - min(tm_values) if tm_values else 0.0
    metadata_tags = sorted({
        tag
        for primer in primers
        for tag in primer.get("metadata_tags", [])
    })
    return {
        "primer_sets": len(primers),
        "primer_warnings": warning_count,
        "primer_state": "review" if warning_count else "ok",
        "metadata_tags": metadata_tags,
        "tm_span": tm_span,
    }


def _restriction_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise restriction digest guardrail metadata."""

    # purpose: propagate kinetics, buffer, and tag details to asset views
    alerts = result.get("alerts", [])
    digests = result.get("digests", [])
    metadata_tags = sorted({
        tag
        for digest in digests
        for tag in digest.get("metadata_tags", [])
    })
    buffers = sorted({
        (digest.get("buffer") or {}).get("name")
        for digest in digests
        if (digest.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for digest in digests
        for profile in digest.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "restriction_alerts": alerts,
        "restriction_state": "review" if alerts else "ok",
        "metadata_tags": metadata_tags,
        "buffers": buffers,
        "kinetics": kinetics,
    }


def _assembly_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise assembly simulation outputs for guardrails."""

    # purpose: align asset summaries with planner assembly heuristics
    success = result.get("average_success", 0.0)
    state = "ok" if success >= 0.7 else "review"
    steps = result.get("steps", [])
    metadata_tags = sorted({
        tag
        for step in steps
        for tag in step.get("metadata_tags", [])
    })
    ligation_profiles = sorted({
        (step.get("ligation_profile") or {}).get("strategy")
        for step in steps
        if (step.get("ligation_profile") or {}).get("strategy")
    })
    buffers = sorted({
        (step.get("buffer") or {}).get("name")
        for step in steps
        if (step.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for step in steps
        for profile in step.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "assembly_success": success,
        "assembly_state": state,
        "metadata_tags": metadata_tags,
        "ligation_profiles": ligation_profiles,
        "buffers": buffers,
        "kinetics": kinetics,
    }


def _kinetics_summary(digest: dict[str, Any], assembly: dict[str, Any]) -> dict[str, Any]:
    """Aggregate kinetics descriptors across digest and assembly outputs."""

    # purpose: provide reusable kinetics summaries for DNA asset serialization
    enzymes: set[str] = set()
    buffers: set[str] = set()
    ligation_profiles: set[str] = set()
    metadata_tags: set[str] = set()
    for entry in digest.get("digests", []):
        metadata_tags.update(entry.get("metadata_tags", []))
        buffer = (entry.get("buffer") or {}).get("name")
        if buffer:
            buffers.add(buffer)
        for profile in entry.get("kinetics_profiles", []):
            if profile.get("name"):
                enzymes.add(profile["name"])
            metadata_tags.update(profile.get("metadata_tags", []))
    for step in assembly.get("steps", []):
        metadata_tags.update(step.get("metadata_tags", []))
        buffer = (step.get("buffer") or {}).get("name")
        if buffer:
            buffers.add(buffer)
        ligation = step.get("ligation_profile") or {}
        strategy = ligation.get("strategy")
        if strategy:
            ligation_profiles.add(strategy)
        for profile in step.get("kinetics_profiles", []):
            if profile.get("name"):
                enzymes.add(profile["name"])
            metadata_tags.update(profile.get("metadata_tags", []))
    return {
        "enzymes": sorted(enzymes),
        "buffers": sorted(buffers),
        "ligation_profiles": sorted(ligation_profiles),
        "metadata_tags": sorted(metadata_tags),
    }


def _analyse_sequence_guardrails(sequence: str, profile: SequenceToolkitProfile) -> dict[str, Any]:
    """Run toolkit analyses to derive guardrail and kinetics summaries."""

    # purpose: ensure DNA asset serialization reflects kinetics-aware toolkit outputs
    template = [{"name": "asset_version", "sequence": sequence}]
    primer_payload = sequence_toolkit.design_primers(template, config=profile)
    digest_payload = sequence_toolkit.analyze_restriction_digest(template, config=profile)
    assembly_payload = sequence_toolkit.simulate_assembly(
        primer_payload,
        digest_payload,
        config=profile,
        strategy=profile.assembly.strategy,
    )
    guardrails = {
        "primers": _primer_guardrail_summary(primer_payload),
        "restriction": _restriction_guardrail_summary(digest_payload),
        "assembly": _assembly_guardrail_summary(assembly_payload),
    }
    kinetics = _kinetics_summary(digest_payload, assembly_payload)
    presets = sorted({profile.assembly.strategy} | {
        step.get("strategy")
        for step in assembly_payload.get("steps", [])
        if step.get("strategy")
    })
    ligation_strategies = {
        (step.get("ligation_profile") or {}).get("strategy")
        for step in assembly_payload.get("steps", [])
        if (step.get("ligation_profile") or {}).get("strategy")
    }
    presets = sorted({preset for preset in presets + list(ligation_strategies) if preset})
    return {
        "guardrails": guardrails,
        "kinetics": kinetics,
        "assembly_presets": presets,
    }


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
    analysis = _analyse_sequence_guardrails(version.sequence, _DEFAULT_PROFILE)
    kinetics_summary = DNAAssetKineticsSummary(**analysis["kinetics"])
    guardrails = DNAAssetGuardrailHeuristics(**analysis["guardrails"])
    return DNAAssetVersionOut(
        id=version.id,
        version_index=version.version_index,
        sequence_length=version.sequence_length,
        gc_content=version.gc_content,
        created_at=version.created_at,
        created_by_id=version.created_by_id,
        metadata=version.meta or {},
        annotations=annotations,
        kinetics_summary=kinetics_summary,
        assembly_presets=analysis["assembly_presets"],
        guardrail_heuristics=guardrails,
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

