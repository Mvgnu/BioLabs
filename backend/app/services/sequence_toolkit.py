"""Scientific sequence analysis helpers for cloning planner orchestration."""

# purpose: provide deterministic scientific computations shared across planner and dna asset workflows
# status: experimental
# depends_on: primer3, backend.app.sequence
# related_docs: docs/planning/cloning_planner_scope.md, docs/dna_assets.md

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean
from typing import Any

import primer3

from .. import sequence as sequence_utils
from ..data.loaders import (
    get_assembly_strategy_catalog,
    get_buffer_catalog,
    get_enzyme_catalog as load_enzyme_catalog,
)
from ..schemas.sequence_toolkit import (
    AssemblySimulationConfig,
    AssemblySimulationResult,
    AssemblyStepMetrics,
    AssemblyStrategyProfile,
    EnzymeMetadata,
    PrimerCandidate,
    PrimerDesignConfig,
    PrimerDesignRecord,
    PrimerDesignResponse,
    PrimerDesignSummary,
    PrimerThermodynamics,
    QCConfig,
    QCReport,
    QCReportResponse,
    ReactionBuffer,
    RestrictionDigestConfig,
    RestrictionDigestResponse,
    RestrictionDigestResult,
    RestrictionDigestSite,
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
    hairpin_delta_g: float | None = None
    homodimer_delta_g: float | None = None


@dataclass
class PrimerSet:
    """Forward and reverse primer pairing for a template."""

    # purpose: capture matched primer statistics for downstream assembly planning
    # status: experimental
    forward: PrimerDesignResult
    reverse: PrimerDesignResult
    product_size: int
    warnings: list[str]


_GAS_CONSTANT = 1.987
_NEAREST_NEIGHBOR_PARAMS: dict[str, tuple[float, float]] = {
    "AA": (-7.9, -22.2),
    "TT": (-7.9, -22.2),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7),
    "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4),
    "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0),
    "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2),
    "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9),
    "CC": (-8.0, -19.9),
}


def _normalize_sequence(seq: str) -> str:
    """Return uppercase DNA sequence replacing U with T."""

    # purpose: create canonical uppercase DNA sequences for downstream heuristics
    normalized = (seq or "").upper().replace("U", "T")
    return normalized


def _reverse_complement(seq: str) -> str:
    """Return reverse complement of DNA sequence."""

    table = str.maketrans("ACGTN", "TGCAN")
    return _normalize_sequence(seq).translate(table)[::-1]


def _nearest_neighbor_tm(
    seq: str,
    *,
    na_conc_mM: float,
    primer_conc_nM: float,
) -> float:
    """Compute melting temperature using nearest-neighbor thermodynamics."""

    # purpose: provide calibrated tm scores for primer evaluation and guardrails
    sequence = _normalize_sequence(seq)
    if len(sequence) < 2:
        return 0.0
    delta_h = 0.0
    delta_s = 0.0
    for i in range(len(sequence) - 1):
        pair = sequence[i : i + 2]
        if pair not in _NEAREST_NEIGHBOR_PARAMS:
            pair = pair[::-1]
        enthalpy, entropy = _NEAREST_NEIGHBOR_PARAMS.get(pair, (-7.0, -20.0))
        delta_h += enthalpy
        delta_s += entropy
    delta_h *= 1000  # convert to cal/mol
    primer_conc = max(primer_conc_nM * 1e-9, 1e-12)
    salt_conc = max(na_conc_mM * 1e-3, 1e-6)
    denominator = delta_s + (_GAS_CONSTANT * math.log(primer_conc / 4))
    if denominator == 0:
        return 0.0
    tm_kelvin = (delta_h / denominator) + (16.6 * math.log10(salt_conc))
    tm_celsius = tm_kelvin - 273.15
    return max(0.0, tm_celsius)


def _max_hairpin_run(seq: str) -> int:
    """Estimate longest complement run contributing to hairpin formation."""

    # purpose: approximate secondary structure risk for single primers
    sequence = _normalize_sequence(seq)
    rc = _reverse_complement(sequence)
    max_run = 0
    for offset in range(3, len(sequence)):
        run = 0
        for idx in range(len(sequence) - offset):
            if sequence[idx] == rc[offset + idx]:
                run += 1
                if run > max_run:
                    max_run = run
            else:
                run = 0
    return max_run


def _max_homodimer_run(seq: str) -> int:
    """Estimate longest homodimer complement run."""

    # purpose: approximate homodimerization risk for primer validation
    sequence = _normalize_sequence(seq)
    rc = _reverse_complement(sequence)
    max_run = 0
    for offset in range(len(sequence)):
        run = 0
        for idx in range(len(sequence) - offset):
            if sequence[offset + idx] == rc[idx]:
                run += 1
                if run > max_run:
                    max_run = run
            else:
                run = 0
    return max_run


def _delta_g_from_run(match_length: int) -> float | None:
    """Convert contiguous complement run length to approximate ΔG."""

    # purpose: derive thermodynamic penalties from complement run length heuristics
    if match_length < 4:
        return None
    return -1.5 * (match_length - 3)


def _thermodynamic_profile(
    sequence: str, primer_config: PrimerDesignConfig
) -> tuple[float, float | None, float | None]:
    """Return tm and secondary structure heuristics for a primer."""

    # purpose: standardize tm/ΔG metrics used across planner workflows
    tm_value = _nearest_neighbor_tm(
        sequence,
        na_conc_mM=primer_config.na_concentration_mM,
        primer_conc_nM=primer_config.primer_concentration_nM,
    )
    hairpin_match = _max_hairpin_run(sequence)
    homodimer_match = _max_homodimer_run(sequence)
    return tm_value, _delta_g_from_run(hairpin_match), _delta_g_from_run(homodimer_match)


@lru_cache(maxsize=1)
def get_enzyme_catalog() -> list[EnzymeMetadata]:
    """Load and cache curated enzyme metadata records."""

    # purpose: surface curated restriction enzyme metadata for repeated lookups
    return [EnzymeMetadata(**entry) for entry in load_enzyme_catalog()]


@lru_cache(maxsize=1)
def get_reaction_buffers() -> list[ReactionBuffer]:
    """Return curated reaction buffer metadata records."""

    # purpose: provide buffer context for restriction digests and assembly heuristics
    return [ReactionBuffer(**entry) for entry in get_buffer_catalog()]


@lru_cache(maxsize=1)
def get_assembly_strategies() -> list[AssemblyStrategyProfile]:
    """Return catalogued assembly strategy descriptors."""

    # purpose: expose reusable assembly heuristics for planners and governance tooling
    return [
        AssemblyStrategyProfile(**entry)
        for entry in get_assembly_strategy_catalog()
    ]


def _enzyme_index() -> dict[str, EnzymeMetadata]:
    """Return catalog records keyed by normalized enzyme name."""

    # purpose: accelerate metadata lookups during digest analysis
    return {record.name.lower(): record for record in get_enzyme_catalog()}


def _buffer_index() -> dict[str, ReactionBuffer]:
    """Return buffer metadata keyed by normalized buffer name."""

    # purpose: support quick lookup of buffer compatibility heuristics
    return {record.name.lower(): record for record in get_reaction_buffers()}


def _assembly_strategy_index() -> dict[str, AssemblyStrategyProfile]:
    """Return assembly strategy descriptors keyed by normalized name."""

    # purpose: accelerate strategy lookups during simulation scoring
    return {record.name.lower(): record for record in get_assembly_strategies()}


def _kinetics_modifier(
    kinetics_model: str, tm_delta: float, site_count: int, heuristics: dict[str, Any]
) -> float:
    """Return modifier scaling based on strategy kinetics assumptions."""

    # purpose: translate kinetics heuristics into normalized modifiers for simulations
    base = 1.0
    model = (kinetics_model or "unspecified").lower()
    overlap_delta = heuristics.get("overlap_delta", 0.0)
    if model == "type_iis_pulsed":
        diversity = heuristics.get("overhang_diversity", site_count)
        base -= min(0.35, max(0.0, 4 - diversity) * 0.05)
        base -= min(0.1, max(0.0, tm_delta - 3.0) * 0.02)
    elif model == "isothermal_exonuclease":
        base -= min(0.3, overlap_delta * 0.01)
        base -= min(0.2, max(0.0, tm_delta - 2.5) * 0.02)
    elif model == "high_fidelity":
        base -= min(0.15, max(0.0, tm_delta - 1.5) * 0.015)
        base -= min(0.1, max(0.0, heuristics.get("buffer_penalty", 0.0)) * 0.5)
    elif model == "recombinase_mediated":
        base -= min(0.4, max(0, 2 - site_count) * 0.12)
        base -= min(0.2, overlap_delta * 0.008)
    else:
        base -= min(0.2, max(0.0, tm_delta - 2.0) * 0.02)
    return max(0.1, min(1.0, base))


def _primer_candidate_from_result(result: PrimerDesignResult) -> PrimerCandidate:
    """Convert dataclass metrics into a schema candidate object."""

    # purpose: translate internal dataclass metrics into Pydantic schema payloads
    thermo = PrimerThermodynamics(
        tm=result.tm,
        gc_content=result.gc_content,
        hairpin_delta_g=result.hairpin_delta_g,
        homodimer_delta_g=result.homodimer_delta_g,
    )
    return PrimerCandidate(
        sequence=result.sequence,
        start=result.start,
        length=result.length,
        thermodynamics=thermo,
    )


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
        base = base.model_copy(update={"enzymes": list(enzymes)})
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
        base = base.model_copy(update={"strategy": strategy})
    strategy_entry = _assembly_strategy_index().get(base.strategy.lower())
    if strategy_entry:
        update_payload = {
            "base_success": strategy_entry.base_success,
            "tm_penalty_factor": strategy_entry.tm_penalty_factor,
            "minimal_site_count": strategy_entry.minimal_site_count,
            "low_site_penalty": strategy_entry.low_site_penalty,
            "ligation_efficiency": strategy_entry.ligation_efficiency,
            "kinetics_model": strategy_entry.kinetics_model,
            "overlap_optimum": strategy_entry.overlap_optimum,
            "overlap_tolerance": strategy_entry.overlap_tolerance,
            "overhang_diversity_factor": strategy_entry.overhang_diversity_factor,
        }
        base = base.model_copy(update=update_payload)
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
    records: list[PrimerDesignRecord] = []
    tm_values: list[float] = []
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = (descriptor.get("sequence") or "").upper()
        if len(template) < size_range[0]:
            records.append(
                PrimerDesignRecord(
                    name=name,
                    status="insufficient_sequence",
                    notes=[
                        f"Sequence length {len(template)} below minimum {size_range[0]}",
                    ],
                )
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
            "PRIMER_GC_CLAMP": primer_config.gc_clamp_min,
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
        forward_tm, forward_hairpin, forward_dimer = _thermodynamic_profile(
            forward_seq, primer_config
        )
        reverse_tm, reverse_hairpin, reverse_dimer = _thermodynamic_profile(
            reverse_seq, primer_config
        )
        forward = PrimerDesignResult(
            sequence=forward_seq,
            tm=(
                forward_stats or {"tm": design.get("PRIMER_LEFT_0_TM", forward_tm)}
            )["tm"],
            gc_content=(forward_stats or {"gc_content": _gc_content(forward_seq)})[
                "gc_content"
            ],
            start=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[0],
            length=(design.get("PRIMER_LEFT_0") or (0, len(forward_seq)))[1],
            hairpin_delta_g=forward_hairpin,
            homodimer_delta_g=forward_dimer,
        )
        reverse = PrimerDesignResult(
            sequence=reverse_seq,
            tm=(
                reverse_stats or {"tm": design.get("PRIMER_RIGHT_0_TM", reverse_tm)}
            )["tm"],
            gc_content=(reverse_stats or {"gc_content": _gc_content(reverse_seq)})[
                "gc_content"
            ],
            start=(
                design.get("PRIMER_RIGHT_0")
                or (len(template) - len(reverse_seq), len(reverse_seq))
            )[0],
            length=(
                design.get("PRIMER_RIGHT_0")
                or (len(reverse_seq), len(reverse_seq))
            )[1],
            hairpin_delta_g=reverse_hairpin,
            homodimer_delta_g=reverse_dimer,
        )
        product_size = design.get("PRIMER_PAIR_0_PRODUCT_SIZE") or len(template)
        tm_values.extend([forward.tm, reverse.tm])
        warnings: list[str] = []
        notes: list[str] = []
        if primer_source == "fallback":
            notes.append("Primer3 returned no candidates; deterministic fallback used.")
        tm_delta = abs(forward.tm - reverse.tm)
        if tm_delta > 2.0:
            warnings.append(f"Primer Tm delta {tm_delta:.2f} exceeds tolerance")
        gc_delta = abs(forward.gc_content - reverse.gc_content)
        if gc_delta > 10:
            warnings.append(f"Primer GC delta {gc_delta:.2f} exceeds tolerance")
        forward_clamp = sum(
            1 for base in forward.sequence[-primer_config.gc_clamp_max :] if base in {"G", "C"}
        )
        reverse_clamp = sum(
            1 for base in reverse.sequence[-primer_config.gc_clamp_max :] if base in {"G", "C"}
        )
        if forward_clamp < primer_config.gc_clamp_min or reverse_clamp < primer_config.gc_clamp_min:
            warnings.append("GC clamp below configured minimum")
        if forward.hairpin_delta_g and forward.hairpin_delta_g < -6:
            warnings.append(
                f"Forward primer predicted hairpin ΔG {forward.hairpin_delta_g:.2f} kcal/mol"
            )
        if reverse.hairpin_delta_g and reverse.hairpin_delta_g < -6:
            warnings.append(
                f"Reverse primer predicted hairpin ΔG {reverse.hairpin_delta_g:.2f} kcal/mol"
            )
        if forward.homodimer_delta_g and forward.homodimer_delta_g < -6:
            warnings.append(
                f"Forward primer homodimer ΔG {forward.homodimer_delta_g:.2f} kcal/mol"
            )
        if reverse.homodimer_delta_g and reverse.homodimer_delta_g < -6:
            warnings.append(
                f"Reverse primer homodimer ΔG {reverse.homodimer_delta_g:.2f} kcal/mol"
            )
        records.append(
            PrimerDesignRecord(
                name=name,
                status="ok",
                forward=_primer_candidate_from_result(forward),
                reverse=_primer_candidate_from_result(reverse),
                product_size=product_size,
                warnings=warnings,
                source=primer_source,
                notes=notes,
            )
        )
    if tm_values:
        summary = PrimerDesignSummary(
            primer_count=len(tm_values) // 2,
            average_tm=mean(tm_values),
            min_tm=min(tm_values),
            max_tm=max(tm_values),
        )
    else:
        summary = PrimerDesignSummary(
            primer_count=0,
            average_tm=0.0,
            min_tm=0.0,
            max_tm=0.0,
        )
    return PrimerDesignResponse(primers=records, summary=summary).model_dump()


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
    catalog_index = _enzyme_index()
    buffer_catalog = _buffer_index()
    enzyme_catalog: list[EnzymeMetadata] = []
    digest_results: list[RestrictionDigestResult] = []
    compatibility_alerts: list[str] = []
    metadata_alerts: list[str] = []
    selected_buffer = None
    if digest_config.reaction_buffer:
        selected_buffer = buffer_catalog.get(
            digest_config.reaction_buffer.lower()
        )
        if not selected_buffer:
            metadata_alerts.append(
                f"Reaction buffer {digest_config.reaction_buffer} not found in catalog"
            )
    for enzyme_name in enzyme_list:
        meta = catalog_index.get(enzyme_name.lower())
        if meta:
            enzyme_catalog.append(meta)
        else:
            metadata_alerts.append(f"No catalog metadata available for {enzyme_name}")
            enzyme_catalog.append(
                EnzymeMetadata(
                    name=enzyme_name,
                    recognition_site="unknown",
                    compatible_buffers=[],
                )
            )
    for descriptor in template_sequences:
        name = descriptor.get("name") or descriptor.get("id") or "template"
        template = descriptor.get("sequence") or ""
        site_map = sequence_utils.restriction_map(template, enzyme_list)
        if digest_config.require_all:
            compatible = all(len(positions) > 0 for positions in site_map.values())
        else:
            compatible = any(len(positions) > 0 for positions in site_map.values())
        buffer_alerts: list[str] = []
        site_payload: dict[str, RestrictionDigestSite] = {}
        for enzyme_name, positions in site_map.items():
            meta = catalog_index.get(enzyme_name.lower())
            if digest_config.reaction_buffer and meta:
                if digest_config.reaction_buffer not in meta.compatible_buffers:
                    buffer_alerts.append(
                        f"{enzyme_name} not validated for buffer {digest_config.reaction_buffer}"
                    )
            site_payload[enzyme_name] = RestrictionDigestSite(
                enzyme=enzyme_name,
                positions=positions,
                recognition_site=(meta.recognition_site if meta else None),
                metadata=meta,
            )
        digest_notes: list[str] = []
        for enzyme_name, meta in ((entry.name, entry) for entry in enzyme_catalog):
            if meta.star_activity_notes:
                digest_notes.append(f"{enzyme_name}: {meta.star_activity_notes}")
        if selected_buffer:
            digest_notes.append(
                f"Buffer {selected_buffer.name}: {selected_buffer.notes or 'no notes recorded.'}"
            )
        digest_results.append(
            RestrictionDigestResult(
                name=name,
                sites=site_payload,
                compatible=compatible,
                buffer_alerts=buffer_alerts,
                notes=digest_notes,
                buffer=selected_buffer,
            )
        )
        absent_enzymes = [enz for enz, positions in site_map.items() if not positions]
        if absent_enzymes:
            compatibility_alerts.append(
                f"{name} lacks cut sites for {', '.join(absent_enzymes)}"
            )
    return RestrictionDigestResponse(
        enzymes=enzyme_catalog,
        digests=digest_results,
        alerts=compatibility_alerts + metadata_alerts,
    ).model_dump()


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
    steps: list[AssemblyStepMetrics] = []
    success_scores: list[float] = []
    primers = primer_results.get("primers", [])
    digests = {
        item["name"]: item for item in digest_results.get("digests", [])
    }
    for entry in primers:
        name = entry.get("name")
        digest = digests.get(name, {})
        tm_delta = 0.0
        if entry.get("status") == "ok":
            forward_tm = entry["forward"]["thermodynamics"]["tm"]
            reverse_tm = entry["reverse"]["thermodynamics"]["tm"]
            tm_delta = abs(forward_tm - reverse_tm)
        site_count = 0
        overhang_signatures: set[str] = set()
        for site in digest.get("sites", {}).values():
            if isinstance(site, dict):
                site_positions = site.get("positions", [])
            else:
                site_positions = site
            site_count += len(site_positions)
            if isinstance(site, dict):
                site_meta = site.get("metadata") or {}
                overhang = site_meta.get("overhang") or site_meta.get("recognition_site")
                if overhang:
                    overhang_signatures.add(str(overhang))
        overhang_diversity = len(overhang_signatures) or site_count
        buffer_penalty = 0.0
        if digest.get("buffer_alerts"):
            buffer_penalty += min(0.3, 0.05 * len(digest["buffer_alerts"]))
        buffer_meta = digest.get("buffer") or {}
        compatible_strategies = buffer_meta.get("compatible_strategies", [])
        if (
            compatible_strategies
            and assembly_config.strategy not in compatible_strategies
        ):
            buffer_penalty += 0.1
        product_size = entry.get("product_size") or 0
        forward_len = (entry.get("forward") or {}).get("length") or 0
        reverse_len = (entry.get("reverse") or {}).get("length") or 0
        overlap_estimate = max(0, product_size - (forward_len + reverse_len))
        overlap_delta = 0.0
        if assembly_config.overlap_optimum is not None:
            overlap_delta = abs(
                overlap_estimate - assembly_config.overlap_optimum
            )
        heuristics = {
            "tm_delta": tm_delta,
            "site_count": float(site_count),
            "buffer_penalty": buffer_penalty,
            "overlap_estimate": overlap_estimate,
            "overhang_diversity": float(overhang_diversity),
        }
        if assembly_config.overlap_tolerance:
            heuristics["overlap_tolerance"] = assembly_config.overlap_tolerance
        if overlap_delta:
            heuristics["overlap_delta"] = overlap_delta
        score = (
            assembly_config.base_success
            - (tm_delta * assembly_config.tm_penalty_factor)
            - buffer_penalty
        )
        if site_count < assembly_config.minimal_site_count:
            score *= assembly_config.low_site_penalty
        ligation_efficiency = assembly_config.ligation_efficiency
        score *= ligation_efficiency
        kinetics_score = _kinetics_modifier(
            assembly_config.kinetics_model,
            tm_delta,
            site_count,
            heuristics,
        )
        heuristics["kinetics_modifier"] = kinetics_score
        score *= kinetics_score
        score = max(0.0, min(1.0, score))
        success_scores.append(score)
        warnings = list(entry.get("warnings", []))
        if kinetics_score < 0.6:
            warnings.append(
                "Kinetics model predicts suboptimal junction progression"
            )
        steps.append(
            AssemblyStepMetrics(
                template=name,
                strategy=assembly_config.strategy,
                expected_fragment_count=max(1, site_count),
                junction_success=score,
                ligation_efficiency=ligation_efficiency,
                kinetics_score=kinetics_score,
                heuristics=heuristics,
                warnings=warnings,
            )
        )
    return AssemblySimulationResult(
        strategy=assembly_config.strategy,
        steps=steps,
        average_success=mean(success_scores) if success_scores else 0.0,
        min_success=min(success_scores) if success_scores else 0.0,
        max_success=max(success_scores) if success_scores else 0.0,
    ).model_dump()


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
    reports: list[QCReport] = []
    for step in assembly_plan.get("steps", []):
        status = (
            "pass"
            if step.get("junction_success", 0.0) >= qc_config.junction_pass_threshold
            else "review"
        )
        reports.append(
            QCReport(
                template=step.get("template"),
                checkpoint="assembly_quality",
                status=status,
                details={
                    "junction_success": step.get("junction_success"),
                    "strategy": assembly_plan.get("strategy"),
                },
            )
        )
    for chromatogram in chromatograms or []:
        qc_status = (
            "pass"
            if chromatogram.get("mismatch_rate", 0.0)
            <= qc_config.chromatogram_mismatch_threshold
            else "review"
        )
        reports.append(
            QCReport(
                template=chromatogram.get("template"),
                checkpoint="chromatogram_validation",
                status=qc_status,
                details=dict(chromatogram),
            )
        )
    return QCReportResponse(reports=reports).model_dump()
