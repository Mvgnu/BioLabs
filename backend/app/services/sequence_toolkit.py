"""Scientific sequence analysis helpers for cloning planner orchestration."""

# purpose: provide deterministic scientific computations shared across planner and dna asset workflows
# status: experimental
# depends_on: primer3, backend.app.sequence
# related_docs: docs/planning/cloning_planner_scope.md, docs/dna_assets.md

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Any

import primer3

from .. import sequence as sequence_utils
from ..schemas.sequence_toolkit import (
    AssemblySimulationConfig,
    PrimerDesignConfig,
    QCConfig,
    RestrictionDigestConfig,
    SequenceToolkitProfile,
)


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


def compute_sequence_metrics(sequence: str) -> dict[str, Any]:
    """Return basic length and GC metrics for a sequence."""

    # purpose: provide reusable metrics for DNA asset summaries and planner telemetry
    normalized = (sequence or "").upper()
    return {
        "length": len(normalized),
        "gc_content": _gc_content(normalized),
    }


def diff_sequences(reference: str, candidate: str) -> dict[str, int]:
    """Return substitution/insertion/deletion counts between two sequences."""

    # purpose: supply lightweight diff statistics for DNA asset guardrail enforcement
    ref = reference or ""
    cand = candidate or ""
    substitutions = sum(1 for a, b in zip(ref, cand) if a != b)
    insertions = max(len(cand) - len(ref), 0)
    deletions = max(len(ref) - len(cand), 0)
    return {
        "substitutions": substitutions,
        "insertions": insertions,
        "deletions": deletions,
    }


def _resolve_primer_config(
    config: PrimerDesignConfig | SequenceToolkitProfile | None,
    *,
    product_size_range: tuple[int, int] | None,
    target_tm: float | None,
) -> tuple[PrimerDesignConfig, tuple[int, int], float]:
    if isinstance(config, SequenceToolkitProfile):
        base = config.primer
    elif isinstance(config, PrimerDesignConfig):
        base = config
    else:
        base = PrimerDesignConfig()
    size_range = product_size_range or base.product_size_range
    tm = target_tm if target_tm is not None else base.target_tm
    return base, size_range, tm


def _resolve_restriction_config(
    config: RestrictionDigestConfig | SequenceToolkitProfile | None,
    *,
    enzymes: Sequence[str] | None,
) -> RestrictionDigestConfig:
    if isinstance(config, SequenceToolkitProfile):
        base = config.restriction
    elif isinstance(config, RestrictionDigestConfig):
        base = config
    else:
        base = RestrictionDigestConfig()
    if enzymes:
        base = base.copy(update={"enzymes": list(enzymes)})
    return base


def _resolve_assembly_config(
    config: AssemblySimulationConfig | SequenceToolkitProfile | None,
    *,
    strategy: str | None,
) -> AssemblySimulationConfig:
    if isinstance(config, SequenceToolkitProfile):
        base = config.assembly
    elif isinstance(config, AssemblySimulationConfig):
        base = config
    else:
        base = AssemblySimulationConfig()
    if strategy:
        base = base.copy(update={"strategy": strategy})
    return base


def _resolve_qc_config(
    config: QCConfig | SequenceToolkitProfile | None,
) -> QCConfig:
    if isinstance(config, SequenceToolkitProfile):
        return config.qc
    if isinstance(config, QCConfig):
        return config
    return QCConfig()


def design_primers(
    template_sequences: Sequence[dict[str, Any]],
    *,
    config: PrimerDesignConfig | SequenceToolkitProfile | None = None,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
) -> dict[str, Any]:
    """Generate primer sets for uploaded templates using Primer3."""

    # purpose: derive thermodynamically-validated primers for planner stages
    # inputs: sequence descriptors with `name` and `sequence` keys
    # outputs: mapping of template names to primer metrics compatible with planner schemas
    # status: experimental
    primer_config, size_range, tm_target = _resolve_primer_config(
        config,
        product_size_range=product_size_range,
        target_tm=target_tm,
    )
    results: dict[str, Any] = {"primers": [], "summary": {}}
    tm_values: list[float] = []
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = (descriptor.get("sequence") or "").upper()
        if len(template) < size_range[0]:
            results["primers"].append(
                {
                    "name": name,
                    "status": "insufficient_sequence",
                    "reason": f"Sequence length {len(template)} below minimum {size_range[0]}",
                }
            )
            continue
        seq_args = {
            "SEQUENCE_ID": name,
            "SEQUENCE_TEMPLATE": template,
        }
        global_args = {
            "PRIMER_PRODUCT_SIZE_RANGE": [list(size_range)],
            "PRIMER_OPT_TM": tm_target,
            "PRIMER_MIN_TM": primer_config.min_tm,
            "PRIMER_MAX_TM": primer_config.max_tm,
            "PRIMER_MIN_SIZE": primer_config.min_size,
            "PRIMER_OPT_SIZE": primer_config.opt_size,
            "PRIMER_MAX_SIZE": primer_config.max_size,
            "PRIMER_NUM_RETURN": primer_config.num_return,
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
            tm=(forward_stats or {"tm": design.get("PRIMER_LEFT_0_TM", tm_target)})["tm"],
            gc_content=(forward_stats or {"gc_content": _gc_content(forward_seq)})["gc_content"],
            start=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[0],
            length=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[1],
        )
        reverse = PrimerDesignResult(
            sequence=reverse_seq,
            tm=(reverse_stats or {"tm": design.get("PRIMER_RIGHT_0_TM", tm_target)})["tm"],
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
    config: RestrictionDigestConfig | SequenceToolkitProfile | None = None,
    enzymes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate restriction sites for templates."""

    # purpose: provide enzyme compatibility scoring for planner assembly strategies
    # inputs: sequence descriptors and optional enzyme list
    # outputs: digest summary keyed by template
    # status: experimental
    digest_config = _resolve_restriction_config(config, enzymes=enzymes)
    enzyme_list = list(digest_config.enzymes)
    digest_results: list[dict[str, Any]] = []
    compatibility_alerts: list[str] = []
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = descriptor.get("sequence") or ""
        site_map = sequence_utils.restriction_map(template, enzyme_list)
        if digest_config.require_all:
            compatible = all(len(positions) > 0 for positions in site_map.values())
        else:
            compatible = any(len(positions) > 0 for positions in site_map.values())
        digest_results.append(
            {
                "name": name,
                "sites": site_map,
                "compatible": compatible,
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
    config: AssemblySimulationConfig | SequenceToolkitProfile | None = None,
    strategy: str | None = None,
) -> dict[str, Any]:
    """Generate assembly plan heuristics."""

    # purpose: estimate assembly junction success probabilities for planner guardrails
    # inputs: primer and restriction digest outputs with selected strategy
    # outputs: plan structure containing steps and success scoring
    # status: experimental
    assembly_config = _resolve_assembly_config(config, strategy=strategy)
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
        score = assembly_config.base_success - (tm_delta * assembly_config.tm_penalty_factor)
        if site_count < assembly_config.minimal_site_count:
            score *= assembly_config.low_site_penalty
        score = max(0.0, min(1.0, score))
        success_scores.append(score)
        steps.append(
            {
                "template": name,
                "strategy": assembly_config.strategy,
                "expected_fragment_count": max(1, site_count),
                "junction_success": score,
                "warnings": entry.get("warnings", []),
            }
        )
    return {
        "strategy": assembly_config.strategy,
        "steps": steps,
        "average_success": mean(success_scores) if success_scores else 0.0,
        "min_success": min(success_scores) if success_scores else 0.0,
        "max_success": max(success_scores) if success_scores else 0.0,
    }


def evaluate_qc_reports(
    assembly_plan: dict[str, Any],
    *,
    config: QCConfig | SequenceToolkitProfile | None = None,
    chromatograms: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Produce QC checkpoints based on assembly outcomes and optional chromatograms."""

    # purpose: surface guardrail gating indicators for planner finalization
    # inputs: assembly plan metrics and optional chromatogram uploads
    # outputs: list of qc assessment dicts consumed by planner responses
    # status: experimental
    qc_config = _resolve_qc_config(config)
    reports: list[dict[str, Any]] = []
    for step in assembly_plan.get("steps", []):
        status = (
            "pass"
            if step.get("junction_success", 0.0) >= qc_config.junction_pass_threshold
            else "review"
        )
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
        qc_status = (
            "pass"
            if chromatogram.get("mismatch_rate", 0.0)
            <= qc_config.chromatogram_mismatch_threshold
            else "review"
        )
        reports.append(
            {
                "template": chromatogram.get("template"),
                "checkpoint": "chromatogram_validation",
                "status": qc_status,
                "details": chromatogram,
            }
        )
    return reports
