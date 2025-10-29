"""DNA asset lifecycle service helpers."""

# purpose: provide persistence, diffing, and governance hooks for DNA asset workflows
# status: experimental
# depends_on: backend.app.models, backend.app.schemas.dna_assets, backend.app.services.sequence_toolkit
# related_docs: docs/dna_assets.md

from __future__ import annotations

import hashlib
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, joinedload

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
    DNAViewerCustodyEscalation,
    DNAViewerCustodyLedgerEntry,
    DNAViewerFeature,
    DNAViewerGovernanceContext,
    DNAViewerGovernanceTimelineEntry,
    DNAViewerGuardrailTimelineEvent,
    DNAViewerLineageBreadcrumb,
    DNAViewerPlannerContext,
    DNAViewerPayload,
    DNAViewerTrack,
    DNAViewerTranslation,
)
from . import cloning_planner, sequence_toolkit

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


_DEFAULT_CAI_REFERENCE: dict[str, float] = {
    codon: (1.0 if codon.endswith(("G", "C")) else 0.78)
    for codon, amino_acid in _CODON_TABLE.items()
    if amino_acid != "*"
}
_DEFAULT_CAI_REFERENCE.update(
    {
        "ATG": 0.95,
        "TTG": 0.82,
        "CTG": 1.0,
        "ATA": 0.7,
        "ATT": 0.75,
        "ATC": 0.9,
        "TTA": 0.68,
        "CTA": 0.7,
        "TGT": 0.85,
        "TGC": 0.95,
        "TGG": 0.95,
        "AGG": 0.72,
        "AGA": 0.7,
    }
)


_MOTIF_LIBRARY: list[dict[str, str]] = [
    {"name": "tata_box", "sequence": "TATAAT"},
    {"name": "pribnow_minus_35", "sequence": "TTGACA"},
    {"name": "gc_clamp", "sequence": "CCGCGG"},
    {"name": "rho_independent_core", "sequence": "GCCGCC"},
]


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


def _compute_translation_frame_summary(
    translations: Sequence[DNAViewerTranslation],
) -> dict[str, Any]:
    """Summarise translation frames represented in the viewer payload."""

    # purpose: expose frame utilisation metrics for analytics overlays
    frame_counts: dict[str, int] = {
        "+1": 0,
        "+2": 0,
        "+3": 0,
        "-1": 0,
        "-2": 0,
        "-3": 0,
    }
    active_labels: set[str] = set()
    for translation in translations:
        key = f"{translation.frame:+d}"
        frame_counts[key] = frame_counts.get(key, 0) + 1
        if translation.amino_acids:
            active_labels.add(translation.label)
    total = sum(frame_counts.values())
    utilisation = {
        frame: round(count / total, 4) if total else 0.0
        for frame, count in frame_counts.items()
    }
    return {
        "counts": frame_counts,
        "utilisation": utilisation,
        "active_labels": sorted(active_labels),
    }


def _compute_codon_adaptation_index(
    sequence: str, *, reference: dict[str, float] | None = None
) -> float:
    """Estimate codon adaptation index using a reference preference table."""

    # purpose: offer governance-aligned codon adaptation heuristics for overlays
    normalised = _normalize_sequence(sequence)
    if len(normalised) < 3:
        return 0.0
    reference = reference or _DEFAULT_CAI_REFERENCE
    weights: list[float] = []
    for index in range(0, len(normalised) - 2, 3):
        codon = normalised[index : index + 3]
        if len(codon) < 3:
            continue
        amino_acid = _CODON_TABLE.get(codon)
        if not amino_acid or amino_acid == "*":
            continue
        weight = reference.get(codon)
        if weight is None:
            amino_acid_codons = [
                candidate
                for candidate, aa in _CODON_TABLE.items()
                if aa == amino_acid and reference.get(candidate)
            ]
            if amino_acid_codons:
                weight = max(reference[candidate] for candidate in amino_acid_codons)
        if weight is None or weight <= 0:
            continue
        weights.append(weight)
    if not weights:
        return 0.0
    log_sum = sum(math.log(weight) for weight in weights)
    return round(math.exp(log_sum / len(weights)), 4)


def _find_motif_hotspots(sequence: str) -> list[dict[str, Any]]:
    """Locate motif occurrences used for risk-aware viewer overlays."""

    # purpose: surface promoter/terminator motifs for governance breadcrumbs
    normalised = _normalize_sequence(sequence)
    if not normalised:
        return []
    findings: list[dict[str, Any]] = []
    for motif in _MOTIF_LIBRARY:
        motif_sequence = motif["sequence"]
        length = len(motif_sequence)
        reverse = _reverse_complement(motif_sequence)
        for index in range(0, len(normalised) - length + 1):
            window = normalised[index : index + length]
            if window == motif_sequence:
                findings.append(
                    {
                        "motif": motif["name"],
                        "start": index + 1,
                        "end": index + length,
                        "strand": 1,
                    }
                )
            if reverse != motif_sequence and window == reverse:
                findings.append(
                    {
                        "motif": motif["name"],
                        "start": index + 1,
                        "end": index + length,
                        "strand": -1,
                    }
                )
    findings.sort(key=lambda item: (item["start"], item["strand"]))
    return findings


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
    mitigations: list[str] = []
    if homopolymers:
        mitigations.append("Introduce sequence edits or primer offsets to disrupt homopolymer runs.")
    if gc_hotspots:
        mitigations.append("Adjust annealing conditions or re-design fragments to diffuse GC hotspots.")
    if primer_warnings:
        mitigations.append("Review primer design heuristics and resolve flagged thermodynamic warnings.")
    if max_gc_skew >= 0.4:
        mitigations.append("Balance GC distribution or lengthen synthesis fragments to dampen skew extremes.")
    if homopolymers or gc_hotspots or primer_warnings or max_gc_skew >= 0.4:
        overall_state = "review"
    return {
        "homopolymers": homopolymers,
        "gc_hotspots": gc_hotspots,
        "primer_tm_span": tm_span,
        "primer_warnings": primer_warnings,
        "max_gc_skew": max_gc_skew,
        "overall_state": overall_state,
        "mitigations": mitigations,
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
    qc_payload = sequence_toolkit.evaluate_qc_reports(
        assembly_payload,
        config=profile,
    )
    recommendations = sequence_toolkit.build_strategy_recommendations(
        template,
        preset_id=profile.preset_id,
        primer_payload=primer_payload,
        restriction_payload=digest_payload,
        assembly_payload=assembly_payload,
        qc_payload=qc_payload,
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
        "toolkit_recommendations": recommendations,
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
    qc_payload = sequence_toolkit.evaluate_qc_reports(
        assembly_payload,
        config=profile,
    )
    recommendations = sequence_toolkit.build_strategy_recommendations(
        template,
        preset_id=profile.preset_id,
        primer_payload=primer_payload,
        restriction_payload=digest_payload,
        assembly_payload=assembly_payload,
        qc_payload=qc_payload,
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
        "toolkit_recommendations": recommendations,
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
        toolkit_recommendations=analysis["toolkit_recommendations"],
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
    db: Session | None = None,
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
    frame_summary = _compute_translation_frame_summary(translations)
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
    cai = _compute_codon_adaptation_index(latest.sequence)
    motif_hotspots = _find_motif_hotspots(latest.sequence)
    analytics = DNAViewerAnalytics(
        codon_usage=_compute_codon_usage(latest.sequence),
        gc_skew=gc_skew,
        thermodynamic_risk=_compute_thermodynamic_risk(
            latest.sequence, guardrails, gc_skew=gc_skew
        ),
        translation_frames=frame_summary,
        codon_adaptation_index=cai,
        motif_hotspots=motif_hotspots,
    )
    governance_context = _build_viewer_governance_context(asset, version_out, db=db)
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
        governance_context=governance_context,
        toolkit_recommendations=version_out.toolkit_recommendations,
    )


def _build_viewer_governance_context(
    asset: models.DNAAsset,
    version_out: DNAAssetVersionOut,
    *,
    db: Session | None = None,
) -> DNAViewerGovernanceContext:
    recent_versions = sorted(asset.versions, key=lambda v: v.version_index)[-6:]
    lineage = [
        DNAViewerLineageBreadcrumb(
            version_id=version.id,
            version_index=version.version_index,
            created_at=version.created_at,
            created_by_id=version.created_by_id,
            sequence_length=version.sequence_length,
            comment=version.comment,
        )
        for version in recent_versions
    ]
    guardrail_history = [
        DNAViewerGuardrailTimelineEvent(
            id=event.id,
            event_type=event.event_type,
            severity=(event.details or {}).get("severity"),
            created_at=event.created_at,
            created_by_id=event.created_by_id,
            details=event.details or {},
        )
        for event in asset.guardrail_events[:10]
    ]
    regulatory_density = _compute_regulatory_feature_density(version_out)
    mitigation_playbooks: set[str] = set()
    for event in asset.guardrail_events:
        details = event.details or {}
        candidates: list[str] = []
        if isinstance(details.get("playbook"), str):
            candidates.append(details["playbook"])
        alias = details.get("mitigation_playbook")
        if isinstance(alias, str):
            candidates.append(alias)
        mitigation_detail = details.get("mitigation")
        if isinstance(mitigation_detail, dict):
            playbook = mitigation_detail.get("playbook")
            if isinstance(playbook, str):
                candidates.append(playbook)
        for candidate in candidates:
            mitigation_playbooks.add(candidate)
        if len(mitigation_playbooks) >= 5:
            break
    custody_logs: list[models.GovernanceSampleCustodyLog] = []
    custody_ledger: list[DNAViewerCustodyLedgerEntry] = []
    custody_escalations: list[DNAViewerCustodyEscalation] = []
    planner_sessions: list[DNAViewerPlannerContext] = []
    timeline: list[DNAViewerGovernanceTimelineEntry] = []
    if db is not None:
        custody_logs = _fetch_custody_logs_for_asset(db, asset.id)
        custody_ledger = [
            _serialise_custody_log_for_viewer(log)
            for log in custody_logs
        ]
        escalation_models = _fetch_custody_escalations_for_asset(db, asset.id)
        custody_escalations = [
            _serialise_custody_escalation_for_viewer(escalation)
            for escalation in escalation_models
        ]
        planner_sessions = _gather_planner_contexts(
            db, custody_logs, escalation_models
        )
        timeline = _compose_governance_timeline(
            guardrail_history=guardrail_history,
            custody_ledger=custody_ledger,
            custody_escalations=custody_escalations,
            planner_sessions=planner_sessions,
        )
    sop_links = sorted(
        _extract_sop_links(asset.guardrail_events, tuple(mitigation_playbooks))
    )
    return DNAViewerGovernanceContext(
        lineage=lineage,
        guardrail_history=guardrail_history,
        regulatory_feature_density=regulatory_density,
        mitigation_playbooks=sorted(mitigation_playbooks),
        custody_ledger=custody_ledger,
        custody_escalations=custody_escalations,
        timeline=timeline,
        planner_sessions=planner_sessions,
        sop_links=sop_links,
    )


def _fetch_custody_logs_for_asset(
    db: Session, asset_id: UUID, *, limit: int = 25
) -> list[models.GovernanceSampleCustodyLog]:
    if limit <= 0:
        return []
    query = (
        db.query(models.GovernanceSampleCustodyLog)
        .options(
            joinedload(models.GovernanceSampleCustodyLog.compartment),
            joinedload(models.GovernanceSampleCustodyLog.asset_version),
        )
        .join(
            models.DNAAssetVersion,
            models.DNAAssetVersion.id
            == models.GovernanceSampleCustodyLog.asset_version_id,
        )
        .filter(models.DNAAssetVersion.asset_id == asset_id)
        .order_by(models.GovernanceSampleCustodyLog.performed_at.desc())
        .limit(limit)
    )
    return query.all()


def _serialise_custody_log_for_viewer(
    log: models.GovernanceSampleCustodyLog,
) -> DNAViewerCustodyLedgerEntry:
    metadata = dict(log.meta or {})
    branch_ref = metadata.get("branch_id") or metadata.get("planner_branch_id")
    if branch_ref is not None:
        branch_ref = str(branch_ref)
    guardrail_flags = (
        [str(flag) for flag in log.guardrail_flags]
        if isinstance(log.guardrail_flags, (list, tuple, set))
        else []
    )
    compartment_label = log.compartment.label if log.compartment else None
    return DNAViewerCustodyLedgerEntry(
        id=log.id,
        performed_at=log.performed_at,
        custody_action=log.custody_action,
        quantity=log.quantity,
        quantity_units=log.quantity_units,
        compartment_label=compartment_label,
        guardrail_flags=guardrail_flags,
        planner_session_id=log.planner_session_id,
        branch_id=branch_ref,
        performed_by_id=log.performed_by_id,
        performed_for_team_id=log.performed_for_team_id,
        notes=log.notes,
        metadata=metadata,
    )


def _fetch_custody_escalations_for_asset(
    db: Session, asset_id: UUID, *, limit: int = 25
) -> list[models.GovernanceCustodyEscalation]:
    if limit <= 0:
        return []
    asset_version_alias = aliased(models.DNAAssetVersion)
    log_alias = aliased(models.GovernanceSampleCustodyLog)
    log_version_alias = aliased(models.DNAAssetVersion)
    query = (
        db.query(models.GovernanceCustodyEscalation)
        .options(
            joinedload(models.GovernanceCustodyEscalation.asset_version),
            joinedload(models.GovernanceCustodyEscalation.compartment),
            joinedload(models.GovernanceCustodyEscalation.log).joinedload(
                models.GovernanceSampleCustodyLog.asset_version
            ),
        )
        .outerjoin(
            asset_version_alias,
            asset_version_alias.id
            == models.GovernanceCustodyEscalation.asset_version_id,
        )
        .outerjoin(
            log_alias,
            log_alias.id == models.GovernanceCustodyEscalation.log_id,
        )
        .outerjoin(
            log_version_alias,
            log_version_alias.id == log_alias.asset_version_id,
        )
        .filter(
            sa.or_(
                asset_version_alias.asset_id == asset_id,
                log_version_alias.asset_id == asset_id,
            )
        )
        .order_by(models.GovernanceCustodyEscalation.created_at.desc())
        .limit(limit)
    )
    return query.all()


def _serialise_custody_escalation_for_viewer(
    escalation: models.GovernanceCustodyEscalation,
) -> DNAViewerCustodyEscalation:
    metadata = dict(escalation.meta or {})
    if escalation.compartment and "compartment_label" not in metadata:
        metadata["compartment_label"] = escalation.compartment.label
    if escalation.notifications:
        metadata.setdefault("notifications", escalation.notifications)
    planner_session_id = None
    if escalation.log and escalation.log.planner_session_id:
        planner_session_id = escalation.log.planner_session_id
    guardrail_flags = (
        [str(flag) for flag in escalation.guardrail_flags]
        if isinstance(escalation.guardrail_flags, (list, tuple, set))
        else []
    )
    asset_version_id = escalation.asset_version_id
    if asset_version_id is None and escalation.log:
        asset_version_id = escalation.log.asset_version_id
    return DNAViewerCustodyEscalation(
        id=escalation.id,
        severity=escalation.severity,
        status=escalation.status,
        reason=escalation.reason,
        created_at=escalation.created_at,
        due_at=escalation.due_at,
        acknowledged_at=escalation.acknowledged_at,
        resolved_at=escalation.resolved_at,
        assigned_to_id=escalation.assigned_to_id,
        planner_session_id=planner_session_id,
        asset_version_id=asset_version_id,
        guardrail_flags=guardrail_flags,
        metadata=metadata,
    )


def _gather_planner_contexts(
    db: Session,
    custody_logs: Sequence[models.GovernanceSampleCustodyLog],
    escalations: Sequence[models.GovernanceCustodyEscalation],
    *,
    limit: int = 5,
) -> list[DNAViewerPlannerContext]:
    session_ids: set[UUID] = set()
    for log in custody_logs:
        if log.planner_session_id:
            session_ids.add(log.planner_session_id)
    for escalation in escalations:
        if escalation.log and escalation.log.planner_session_id:
            session_ids.add(escalation.log.planner_session_id)
    contexts: list[DNAViewerPlannerContext] = []
    for session_id in sorted(session_ids):
        planner_session = db.get(models.CloningPlannerSession, session_id)
        if not planner_session:
            continue
        payload = cloning_planner.serialize_session(planner_session)
        guardrail_state = payload.get("guardrail_state") or {}
        custody_status = guardrail_state.get("custody_status")
        if custody_status is None:
            custody_snapshot = guardrail_state.get("custody")
            if isinstance(custody_snapshot, dict):
                custody_status = custody_snapshot.get("status")
        gate_value = payload.get("guardrail_gate")
        if isinstance(gate_value, dict):
            gate_display = gate_value.get("state") or (
                "active" if gate_value.get("active") else "clear"
            )
        elif gate_value is None:
            gate_display = None
        else:
            gate_display = str(gate_value)
        branch_state = payload.get("branch_state") or {}
        branch_order: list[str] = []
        if isinstance(branch_state, dict):
            order = branch_state.get("order")
            if isinstance(order, list):
                branch_order = [str(entry) for entry in order]
        active_branch = payload.get("active_branch_id")
        if isinstance(active_branch, UUID):
            active_branch_ref = str(active_branch)
        else:
            active_branch_ref = str(active_branch) if active_branch else None
        replay_window = payload.get("replay_window")
        if not isinstance(replay_window, dict):
            replay_window = {}
        recovery_context = payload.get("recovery_context")
        if not isinstance(recovery_context, dict):
            recovery_context = {}
        updated_at = payload.get("updated_at") or planner_session.updated_at
        contexts.append(
            DNAViewerPlannerContext(
                session_id=planner_session.id,
                status=payload.get("status", planner_session.status),
                guardrail_gate=gate_display,
                custody_status=custody_status,
                active_branch_id=active_branch_ref,
                branch_order=branch_order,
                replay_window=replay_window,
                recovery_context=recovery_context,
                updated_at=updated_at,
            )
        )
    contexts.sort(
        key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return contexts[:limit]


def _compose_governance_timeline(
    *,
    guardrail_history: Sequence[DNAViewerGuardrailTimelineEvent],
    custody_ledger: Sequence[DNAViewerCustodyLedgerEntry],
    custody_escalations: Sequence[DNAViewerCustodyEscalation],
    planner_sessions: Sequence[DNAViewerPlannerContext],
    limit: int = 50,
) -> list[DNAViewerGovernanceTimelineEntry]:
    entries: list[DNAViewerGovernanceTimelineEntry] = []
    for event in guardrail_history:
        entries.append(
            DNAViewerGovernanceTimelineEntry(
                id=f"guardrail:{event.id}",
                timestamp=event.created_at,
                source="guardrail",
                title=event.event_type.replace("_", " ").title(),
                severity=event.severity,
                details=event.details,
            )
        )
    for log in custody_ledger:
        metadata = log.metadata or {}
        severity = metadata.get("severity") if isinstance(metadata, dict) else None
        if not isinstance(severity, str):
            severity = None
        details: dict[str, Any] = {
            "compartment": log.compartment_label,
            "planner_session_id": str(log.planner_session_id)
            if log.planner_session_id
            else None,
            "branch_id": log.branch_id,
            "guardrail_flags": log.guardrail_flags,
        }
        if log.notes:
            details["notes"] = log.notes
        if log.quantity is not None:
            details["quantity"] = log.quantity
        if log.quantity_units:
            details["quantity_units"] = log.quantity_units
        if isinstance(metadata, dict) and metadata:
            details["metadata"] = metadata
        entries.append(
            DNAViewerGovernanceTimelineEntry(
                id=f"custody_log:{log.id}",
                timestamp=log.performed_at,
                source="custody_log",
                title=f"Custody {log.custody_action}",
                severity=severity,
                details=details,
            )
        )
    for escalation in custody_escalations:
        details = {
            "status": escalation.status,
            "planner_session_id": str(escalation.planner_session_id)
            if escalation.planner_session_id
            else None,
            "due_at": escalation.due_at,
            "guardrail_flags": escalation.guardrail_flags,
        }
        if escalation.metadata:
            details["metadata"] = escalation.metadata
        entries.append(
            DNAViewerGovernanceTimelineEntry(
                id=f"custody_escalation:{escalation.id}",
                timestamp=escalation.created_at,
                source="custody_escalation",
                title=f"Escalation {escalation.reason}",
                severity=escalation.severity,
                details=details,
            )
        )
    for planner in planner_sessions:
        details = {
            "guardrail_gate": planner.guardrail_gate,
            "custody_status": planner.custody_status,
            "active_branch_id": planner.active_branch_id,
            "branch_order": planner.branch_order,
            "replay_window": planner.replay_window,
            "recovery_context": planner.recovery_context,
        }
        entries.append(
            DNAViewerGovernanceTimelineEntry(
                id=f"planner:{planner.session_id}",
                timestamp=planner.updated_at
                or datetime.min.replace(tzinfo=timezone.utc),
                source="planner",
                title="Planner checkpoint",
                severity=planner.custody_status,
                details=details,
            )
        )
    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
    if limit and len(entries) > limit:
        return entries[:limit]
    return entries


def _extract_sop_links(
    events: Sequence[models.DNAAssetGuardrailEvent],
    mitigation_playbooks: Sequence[str],
) -> set[str]:
    links: set[str] = set()
    for playbook in mitigation_playbooks:
        if isinstance(playbook, str) and playbook.startswith(("http://", "https://", "/")):
            links.add(playbook)
    for event in events:
        details = event.details or {}
        sop_link = details.get("sop_url") or details.get("sop_link")
        if isinstance(sop_link, str) and sop_link.startswith(("http://", "https://", "/")):
            links.add(sop_link)
        sop_links = details.get("sop_links")
        if isinstance(sop_links, (list, tuple, set)):
            for candidate in sop_links:
                if isinstance(candidate, str) and candidate.startswith(("http://", "https://", "/")):
                    links.add(candidate)
        mitigation_info = details.get("mitigation")
        if isinstance(mitigation_info, dict):
            ref = mitigation_info.get("documentation") or mitigation_info.get("link")
            if isinstance(ref, str) and ref.startswith(("http://", "https://", "/")):
                links.add(ref)
    return links


def _compute_regulatory_feature_density(
    version_out: DNAAssetVersionOut,
) -> float | None:
    annotations = version_out.annotations or []
    total = len(annotations)
    if total == 0:
        return None
    regulatory_keywords = {
        "promoter",
        "operator",
        "enhancer",
        "terminator",
        "utr",
        "regulatory",
        "riboswitch",
    }
    matches = 0
    for annotation in annotations:
        feature_type = (annotation.feature_type or "").lower()
        qualifiers = annotation.qualifiers or {}
        qualifier_values = " ".join(
            [
                " ".join(value)
                if isinstance(value, (list, tuple))
                else str(value)
                for value in qualifiers.values()
            ]
        ).lower()
        if any(keyword in feature_type for keyword in regulatory_keywords):
            matches += 1
            continue
        if any(keyword in qualifier_values for keyword in regulatory_keywords):
            matches += 1
    return round(matches / total, 4)

