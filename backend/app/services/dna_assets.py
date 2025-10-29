"""DNA asset lifecycle service helpers."""

# purpose: provide persistence, diffing, and governance hooks for DNA asset workflows
# status: experimental
# depends_on: backend.app.models, backend.app.schemas.dna_assets, backend.app.services.sequence_toolkit
# related_docs: docs/dna_assets.md

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..analytics.governance import invalidate_governance_analytics_cache
from ..schemas import (
    DNAAnnotationOut,
    DNAAnnotationPayload,
    DNAAnnotationSegment,
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
    DNAViewerAnalytics,
    DNAViewerFeature,
    DNAViewerPayload,
    DNAViewerTrack,
    DNAViewerTranslation,
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


_CODON_TABLE: dict[str, str] = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}


def _normalize_sequence(sequence: str) -> str:
    return (sequence or "").upper().replace("U", "T")


def _reverse_complement(sequence: str) -> str:
    table = str.maketrans("ACGTN", "TGCAN")
    return _normalize_sequence(sequence).translate(table)[::-1]


def _translate_codons(sequence: str) -> str:
    normalised = _normalize_sequence(sequence)
    amino_acids: list[str] = []
    for idx in range(0, len(normalised) - 2, 3):
        codon = normalised[idx : idx + 3]
        amino_acids.append(_CODON_TABLE.get(codon, "X"))
    return "".join(amino_acids)


def _compute_codon_usage(sequence: str) -> dict[str, float]:
    """Compute codon utilisation frequencies across the sequence."""

    # purpose: expose codon distribution overlays for viewer analytics
    normalised = _normalize_sequence(sequence)
    if len(normalised) < 3:
        return {}
    counts: Counter[str] = Counter()
    for idx in range(0, len(normalised) - 2, 3):
        codon = normalised[idx : idx + 3]
        if len(codon) < 3:
            continue
        if codon not in _CODON_TABLE:
            continue
        counts[codon] += 1
    total = sum(counts.values())
    if not total:
        return {}
    return {
        codon: round(count / total, 6)
        for codon, count in sorted(counts.items())
    }


def _compute_gc_skew(sequence: str, *, window_size: int | None = None) -> list[float]:
    """Compute GC skew values across sliding windows."""

    # purpose: surface GC bias overlays supporting replication origin analysis
    normalised = _normalize_sequence(sequence)
    if not normalised:
        return []
    length = len(normalised)
    window = window_size or max(50, length // 12)
    window = max(25, min(window, length))
    skews: list[float] = []
    for index in range(0, length, window):
        chunk = normalised[index : index + window]
        if not chunk:
            continue
        g = chunk.count("G")
        c = chunk.count("C")
        if g + c == 0:
            skew = 0.0
        else:
            skew = (g - c) / (g + c)
        skews.append(round(skew, 4))
    return skews


def _find_homopolymer_runs(sequence: str, *, minimum: int = 6) -> list[dict[str, Any]]:
    """Locate long homopolymer runs that drive thermodynamic risk."""

    # purpose: identify hotspots for viewer thermodynamic overlays
    runs: list[dict[str, Any]] = []
    if not sequence:
        return runs
    current_base: str | None = None
    current_length = 0
    current_start = 0
    for index, base in enumerate(sequence, start=1):
        if base == current_base:
            current_length += 1
        else:
            if current_base and current_length >= minimum:
                runs.append(
                    {
                        "base": current_base,
                        "start": current_start,
                        "end": current_start + current_length - 1,
                        "length": current_length,
                    }
                )
            current_base = base
            current_length = 1
            current_start = index
    if current_base and current_length >= minimum:
        runs.append(
            {
                "base": current_base,
                "start": current_start,
                "end": current_start + current_length - 1,
                "length": current_length,
            }
        )
    return runs


def _compute_gc_hotspots(sequence: str, *, threshold: float = 0.68) -> list[dict[str, Any]]:
    """Identify GC-rich windows driving thermodynamic escalation."""

    # purpose: derive overlays for GC-dense domains prone to secondary structure
    normalised = _normalize_sequence(sequence)
    length = len(normalised)
    if not length:
        return []
    window = max(30, length // 20)
    hotspots: list[dict[str, Any]] = []
    for index in range(0, length, window):
        chunk = normalised[index : index + window]
        if not chunk:
            continue
        gc_fraction = (chunk.count("G") + chunk.count("C")) / len(chunk)
        if gc_fraction >= threshold:
            hotspots.append(
                {
                    "start": index + 1,
                    "end": index + len(chunk),
                    "gc_fraction": round(gc_fraction, 4),
                }
            )
    return hotspots


def _compute_thermodynamic_risk(
    sequence: str,
    guardrails: DNAAssetGuardrailHeuristics,
    *,
    gc_skew: list[float] | None = None,
) -> dict[str, Any]:
    """Derive thermodynamic risk overlays for viewer analytics."""

    # purpose: tie importer guardrail heuristics to viewer-facing overlays
    normalised = _normalize_sequence(sequence)
    homopolymers = _find_homopolymer_runs(normalised)
    gc_hotspots = _compute_gc_hotspots(normalised)
    primer_summary = guardrails.primers or {}
    tm_span = primer_summary.get("tm_span")
    primer_warnings = primer_summary.get("primer_warnings", 0)
    max_gc_skew = max((abs(value) for value in gc_skew or []), default=0.0)
    overall_state = "ok"
    if homopolymers or gc_hotspots or primer_warnings or max_gc_skew >= 0.4:
        overall_state = "review"
    return {
        "homopolymers": homopolymers,
        "gc_hotspots": gc_hotspots,
        "primer_tm_span": tm_span,
        "primer_warnings": primer_warnings,
        "max_gc_skew": max_gc_skew,
        "overall_state": overall_state,
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
    details = dict(event.details or {})
    event_type = (event.event_type or "").lower()
    severity = str(details.get("severity", "")).lower()
    if "breach" in event_type or severity in {"critical", "major"}:
        invalidate_governance_analytics_cache(execution_ids=[asset.id])
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


def _annotation_guardrail_badges(
    guardrails: DNAAssetGuardrailHeuristics, annotation: DNAAnnotationOut
) -> list[str]:
    badges: set[str] = set()
    feature_type = (annotation.feature_type or "").lower()
    label = (annotation.label or "").lower()
    primers = guardrails.primers or {}
    restriction = guardrails.restriction or {}
    assembly = guardrails.assembly or {}
    if primers.get("primer_state") == "review" and (
        "primer" in feature_type or "primer" in label
    ):
        badges.add("primer-review")
    for tag in primers.get("metadata_tags", []):
        if tag:
            badges.add(f"primer-tag:{tag}")
    if restriction.get("restriction_state") == "review" and (
        "restriction" in feature_type or "cut" in label
    ):
        badges.add("restriction-review")
    for tag in restriction.get("metadata_tags", []):
        if tag:
            badges.add(f"restriction-tag:{tag}")
    if assembly.get("assembly_state") == "review" and (
        "assembly" in feature_type or "cds" in feature_type
    ):
        badges.add("assembly-review")
    for tag in assembly.get("metadata_tags", []):
        if tag:
            badges.add(f"assembly-tag:{tag}")
    return sorted(badges)


def _guardrail_summary_features(
    guardrails: DNAAssetGuardrailHeuristics, *, length: int
) -> list[DNAViewerFeature]:
    features: list[DNAViewerFeature] = []
    guardrail_segments = [
        ("Primer Guardrails", "guardrail.primer", guardrails.primers or {}),
        ("Restriction Guardrails", "guardrail.restriction", guardrails.restriction or {}),
        ("Assembly Guardrails", "guardrail.assembly", guardrails.assembly or {}),
    ]
    for label, feature_type, payload in guardrail_segments:
        if not payload:
            continue
        badges = [
            str(value)
            for key, value in payload.items()
            if key.endswith("state") and value
        ]
        features.append(
            DNAViewerFeature(
                label=label,
                feature_type=feature_type,
                start=1,
                end=max(1, length),
                strand=None,
                qualifiers=dict(payload),
                guardrail_badges=sorted({badge for badge in badges if badge}),
                segments=[
                    DNAAnnotationSegment(start=1, end=max(1, length), strand=None)
                ],
                provenance_tags=[feature_type],
            )
        )
    return features


def _build_viewer_tracks(
    version_out: DNAAssetVersionOut,
    guardrails: DNAAssetGuardrailHeuristics,
) -> list[DNAViewerTrack]:
    feature_track = DNAViewerTrack(name="Annotations")
    for annotation in version_out.annotations:
        segments: list[DNAAnnotationSegment] = []
        for segment in annotation.segments:
            if isinstance(segment, DNAAnnotationSegment):
                segments.append(segment)
            else:
                segments.append(DNAAnnotationSegment(**segment))
        feature_track.features.append(
            DNAViewerFeature(
                label=annotation.label,
                feature_type=annotation.feature_type,
                start=annotation.start,
                end=annotation.end,
                strand=annotation.strand,
                qualifiers=dict(annotation.qualifiers or {}),
                guardrail_badges=_annotation_guardrail_badges(guardrails, annotation),
                segments=segments,
                provenance_tags=list(annotation.provenance_tags or []),
            )
        )
    guardrail_track = DNAViewerTrack(
        name="Guardrails",
        features=_guardrail_summary_features(guardrails, length=version_out.sequence_length),
    )
    return [feature_track, guardrail_track]


def _generate_translations(
    sequence: str, features: list[DNAViewerFeature]
) -> list[DNAViewerTranslation]:
    translations: list[DNAViewerTranslation] = []
    for feature in features:
        feature_type = (feature.feature_type or "").lower()
        if feature_type not in {"cds", "gene"} and "translation" not in feature.qualifiers:
            continue
        start = max(1, feature.start)
        end = max(start, feature.end)
        subseq = sequence[start - 1 : end]
        strand = feature.strand or 1
        if strand < 0:
            subseq = _reverse_complement(subseq)
        amino_acids = feature.qualifiers.get("translation") or _translate_codons(subseq)
        frame_base = ((start - 1) % 3) + 1
        frame = frame_base if strand >= 0 else -frame_base
        translations.append(
            DNAViewerTranslation(
                label=feature.label,
                frame=frame,
                sequence=subseq,
                amino_acids=amino_acids,
            )
        )
    return translations


def build_viewer_payload(
    asset: models.DNAAsset,
    *,
    compare_to: models.DNAAssetVersion | None = None,
) -> DNAViewerPayload:
    """Generate a viewer-ready payload for the provided DNA asset."""

    # purpose: supply frontend viewers with annotations, guardrails, and diffs
    latest = asset.latest_version
    if latest is None:
        raise ValueError("Asset has no versions to visualise")
    asset_summary = serialize_asset(asset)
    version_out = serialize_version(latest)
    guardrails = version_out.guardrail_heuristics
    tracks = _build_viewer_tracks(version_out, guardrails)
    translations = _generate_translations(latest.sequence, tracks[0].features)
    topology = (
        (asset.meta or {}).get("topology")
        or (latest.meta or {}).get("topology")
        or version_out.metadata.get("topology")
        or ("circular" if "circular" in asset_summary.tags else "linear")
    )
    diff = None
    if compare_to is not None:
        diff = diff_versions(compare_to, latest)
    gc_skew = _compute_gc_skew(latest.sequence)
    analytics = DNAViewerAnalytics(
        codon_usage=_compute_codon_usage(latest.sequence),
        gc_skew=gc_skew,
        thermodynamic_risk=_compute_thermodynamic_risk(
            latest.sequence, guardrails, gc_skew=gc_skew
        ),
    )
    return DNAViewerPayload(
        asset=asset_summary,
        version=version_out,
        sequence=latest.sequence,
        topology=topology,
        tracks=tracks,
        translations=translations,
        kinetics_summary=version_out.kinetics_summary,
        guardrails=guardrails,
        analytics=analytics,
        diff=diff,
    )

