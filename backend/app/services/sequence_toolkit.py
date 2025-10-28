"""Scientific sequence analysis helpers for cloning planner orchestration."""

# purpose: provide deterministic scientific computations shared across planner and dna asset workflows
# status: experimental
# depends_on: primer3, backend.app.sequence
# related_docs: docs/planning/cloning_planner_scope.md

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Any

import primer3

from .. import sequence as sequence_utils


@dataclass
class PrimerDesignResult:
    """Container for primer design statistics."""

    # purpose: represent primer candidates with thermodynamic metrics
    # status: experimental
    sequence: str
    tm: float
    gc_content: float
    start: int
    length: int


@dataclass
class PrimerSet:
    """Forward and reverse primer pairing for a template."""

    # purpose: capture matched primer statistics for downstream assembly planning
    # status: experimental
    forward: PrimerDesignResult
    reverse: PrimerDesignResult
    product_size: int
    warnings: list[str]


def _gc_content(seq: str) -> float:
    """Calculate GC content percentage for a sequence."""

    # purpose: support deterministic GC calculations without external libs
    if not seq:
        return 0.0
    gc = seq.count("G") + seq.count("C")
    return (gc / len(seq)) * 100


def design_primers(
    template_sequences: Sequence[dict[str, Any]],
    *,
    product_size_range: tuple[int, int] = (80, 280),
    target_tm: float = 60.0,
) -> dict[str, Any]:
    """Generate primer sets for uploaded templates using Primer3."""

    # purpose: derive thermodynamically-validated primers for planner stages
    # inputs: sequence descriptors with `name` and `sequence` keys
    # outputs: mapping of template names to primer metrics compatible with planner schemas
    # status: experimental
    results: dict[str, Any] = {"primers": [], "summary": {}}
    tm_values: list[float] = []
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = (descriptor.get("sequence") or "").upper()
        if len(template) < product_size_range[0]:
            results["primers"].append(
                {
                    "name": name,
                    "status": "insufficient_sequence",
                    "reason": f"Sequence length {len(template)} below minimum {product_size_range[0]}",
                }
            )
            continue
        seq_args = {
            "SEQUENCE_ID": name,
            "SEQUENCE_TEMPLATE": template,
        }
        global_args = {
            "PRIMER_PRODUCT_SIZE_RANGE": [list(product_size_range)],
            "PRIMER_OPT_TM": target_tm,
            "PRIMER_MIN_TM": target_tm - 5,
            "PRIMER_MAX_TM": target_tm + 5,
            "PRIMER_MIN_SIZE": 18,
            "PRIMER_OPT_SIZE": 22,
            "PRIMER_MAX_SIZE": 30,
            "PRIMER_NUM_RETURN": 1,
        }
        design = primer3.bindings.designPrimers(seq_args, global_args)
        forward_seq = design.get("PRIMER_LEFT_0_SEQUENCE")
        reverse_seq = design.get("PRIMER_RIGHT_0_SEQUENCE")
        if not forward_seq or not reverse_seq:
            fallback = sequence_utils.design_primers(template)
            forward_stats = fallback["forward"]
            reverse_stats = fallback["reverse"]
            forward_seq = forward_stats["sequence"]
            reverse_seq = reverse_stats["sequence"]
            primer_source = "fallback"
        else:
            forward_stats = None
            reverse_stats = None
            primer_source = "primer3"
        forward = PrimerDesignResult(
            sequence=forward_seq,
            tm=(forward_stats or {"tm": design.get("PRIMER_LEFT_0_TM", target_tm)})["tm"],
            gc_content=(forward_stats or {"gc_content": _gc_content(forward_seq)})["gc_content"],
            start=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[0],
            length=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[1],
        )
        reverse = PrimerDesignResult(
            sequence=reverse_seq,
            tm=(reverse_stats or {"tm": design.get("PRIMER_RIGHT_0_TM", target_tm)})["tm"],
            gc_content=(reverse_stats or {"gc_content": _gc_content(reverse_seq)})["gc_content"],
            start=(design.get("PRIMER_RIGHT_0") or (len(template) - len(reverse_seq), len(reverse_seq)))[0],
            length=(design.get("PRIMER_RIGHT_0") or (len(reverse_seq), len(reverse_seq)))[1],
        )
        product_size = design.get("PRIMER_PAIR_0_PRODUCT_SIZE") or len(template)
        tm_values.extend([forward.tm, reverse.tm])
        warnings: list[str] = []
        tm_delta = abs(forward.tm - reverse.tm)
        if tm_delta > 2.0:
            warnings.append(f"Primer Tm delta {tm_delta:.2f} exceeds tolerance")
        gc_delta = abs(forward.gc_content - reverse.gc_content)
        if gc_delta > 10:
            warnings.append(f"Primer GC delta {gc_delta:.2f} exceeds tolerance")
        results["primers"].append(
            {
                "name": name,
                "status": "ok",
                "forward": forward.__dict__,
                "reverse": reverse.__dict__,
                "product_size": product_size,
                "warnings": warnings,
                "source": primer_source,
            }
        )
    if tm_values:
        results["summary"] = {
            "primer_count": len(tm_values) // 2,
            "average_tm": mean(tm_values),
            "min_tm": min(tm_values),
            "max_tm": max(tm_values),
        }
    else:
        results["summary"] = {"primer_count": 0, "average_tm": 0.0, "min_tm": 0.0, "max_tm": 0.0}
    return results


def analyze_restriction_digest(
    template_sequences: Sequence[dict[str, Any]],
    *,
    enzymes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate restriction sites for templates."""

    # purpose: provide enzyme compatibility scoring for planner assembly strategies
    # inputs: sequence descriptors and optional enzyme list
    # outputs: digest summary keyed by template
    # status: experimental
    enzyme_list = list(enzymes) if enzymes else ["EcoRI", "BamHI", "BsaI", "BsmBI"]
    digest_results: list[dict[str, Any]] = []
    compatibility_alerts: list[str] = []
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = descriptor.get("sequence") or ""
        site_map = sequence_utils.restriction_map(template, enzyme_list)
        digest_results.append(
            {
                "name": name,
                "sites": site_map,
                "compatible": all(len(positions) > 0 for positions in site_map.values()),
            }
        )
        absent_enzymes = [enz for enz, positions in site_map.items() if not positions]
        if absent_enzymes:
            compatibility_alerts.append(
                f"{name} lacks cut sites for {', '.join(absent_enzymes)}"
            )
    return {
        "enzymes": enzyme_list,
        "digests": digest_results,
        "alerts": compatibility_alerts,
    }


def simulate_assembly(
    primer_results: dict[str, Any],
    digest_results: dict[str, Any],
    *,
    strategy: str,
) -> dict[str, Any]:
    """Generate assembly plan heuristics."""

    # purpose: estimate assembly junction success probabilities for planner guardrails
    # inputs: primer and restriction digest outputs with selected strategy
    # outputs: plan structure containing steps and success scoring
    # status: experimental
    steps: list[dict[str, Any]] = []
    success_scores: list[float] = []
    primers = primer_results.get("primers", [])
    digests = {item["name"]: item for item in digest_results.get("digests", [])}
    for entry in primers:
        name = entry.get("name")
        digest = digests.get(name, {})
        tm_delta = 0.0
        if entry.get("status") == "ok":
            forward_tm = entry["forward"]["tm"]
            reverse_tm = entry["reverse"]["tm"]
            tm_delta = abs(forward_tm - reverse_tm)
        site_count = sum(len(positions) for positions in digest.get("sites", {}).values())
        score = max(0.0, 1.0 - (tm_delta / 10.0))
        if site_count < 2:
            score *= 0.6
        success_scores.append(score)
        steps.append(
            {
                "template": name,
                "strategy": strategy,
                "expected_fragment_count": max(1, site_count),
                "junction_success": score,
                "warnings": digest.get("compatible") and entry.get("warnings", []),
            }
        )
    return {
        "strategy": strategy,
        "steps": steps,
        "average_success": mean(success_scores) if success_scores else 0.0,
        "min_success": min(success_scores) if success_scores else 0.0,
        "max_success": max(success_scores) if success_scores else 0.0,
    }


def evaluate_qc_reports(
    assembly_plan: dict[str, Any],
    *,
    chromatograms: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Produce QC checkpoints based on assembly outcomes and optional chromatograms."""

    # purpose: surface guardrail gating indicators for planner finalization
    # inputs: assembly plan metrics and optional chromatogram uploads
    # outputs: list of qc assessment dicts consumed by planner responses
    # status: experimental
    reports: list[dict[str, Any]] = []
    for step in assembly_plan.get("steps", []):
        status = "pass" if step.get("junction_success", 0.0) >= 0.7 else "review"
        reports.append(
            {
                "template": step.get("template"),
                "checkpoint": "assembly_quality",
                "status": status,
                "details": {
                    "junction_success": step.get("junction_success"),
                    "strategy": assembly_plan.get("strategy"),
                },
            }
        )
    for chromatogram in chromatograms or []:
        qc_status = "pass" if chromatogram.get("mismatch_rate", 0.0) < 0.05 else "review"
        reports.append(
            {
                "template": chromatogram.get("template"),
                "checkpoint": "chromatogram_validation",
                "status": qc_status,
                "details": chromatogram,
            }
        )
    return reports
