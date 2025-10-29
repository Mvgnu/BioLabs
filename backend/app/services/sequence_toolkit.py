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
    get_enzyme_kinetics_catalog,
    get_ligation_profile_catalog,
)
from ..schemas.sequence_toolkit import (
    AssemblySimulationConfig,
    AssemblySimulationResult,
    AssemblyStepMetrics,
    AssemblyStrategyProfile,
    EnzymeKineticsProfile,
    EnzymeMetadata,
    LigationEfficiencyProfile,
    PrimerCandidate,
    PrimerDesignConfig,
    PrimerDesignRecord,
    PrimerDesignResponse,
    PrimerDesignSummary,
    PrimerThermodynamics,
    PrimerMultiplexCompatibility,
    PrimerCrossDimerFlag,
    QCConfig,
    QCReport,
    QCReportResponse,
    ReactionBuffer,
    RestrictionDigestConfig,
    RestrictionDigestResponse,
    RestrictionDigestResult,
    RestrictionDigestSite,
    RestrictionStrategyEvaluation,
    SequenceToolkitProfile,
    SequenceToolkitPreset,
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


_PRESET_DEFINITIONS: tuple[SequenceToolkitPreset, ...] = (
    SequenceToolkitPreset(
        preset_id="multiplex",
        name="Multiplex cloning",
        description="Optimises primer thermodynamics for multiplex Golden Gate workflows.",
        primer_overrides=PrimerDesignConfig(
            product_size_range=(120, 240),
            target_tm=62.0,
            min_tm=59.0,
            max_tm=66.0,
            min_size=20,
            opt_size=24,
            max_size=30,
            num_return=3,
            primer_concentration_nM=750.0,
            gc_clamp_min=2,
            gc_clamp_max=3,
        ),
        restriction_overrides=RestrictionDigestConfig(
            enzymes=["BsaI", "BsmBI", "SapI", "BbsI"],
            require_all=False,
            reaction_buffer="CutSmart",
        ),
        assembly_overrides=AssemblySimulationConfig(
            strategy="golden_gate",
            base_success=0.78,
            tm_penalty_factor=0.09,
            minimal_site_count=2,
            low_site_penalty=0.65,
            ligation_efficiency=0.88,
            kinetics_model="type_iis_pulsed",
            overlap_optimum=20,
            overlap_tolerance=6,
            overhang_diversity_factor=6.0,
        ),
        metadata_tags=["preset:multiplex", "workflow:multiplex"],
        recommended_use=[
            "Golden Gate multiplex assemblies",
            "Parallel amplicon enrichment",
        ],
        notes=[
            "Optimised for Type IIS multiplex digestion windows and balanced tm deltas.",
        ],
    ),
    SequenceToolkitPreset(
        preset_id="qpcr",
        name="qPCR validation",
        description="Narrow amplicon and tm window for qPCR guardrail verification.",
        primer_overrides=PrimerDesignConfig(
            product_size_range=(70, 140),
            target_tm=60.5,
            min_tm=59.0,
            max_tm=62.5,
            min_size=18,
            opt_size=20,
            max_size=24,
            num_return=2,
            primer_concentration_nM=400.0,
            na_concentration_mM=30.0,
            gc_clamp_min=1,
            gc_clamp_max=2,
        ),
        restriction_overrides=RestrictionDigestConfig(
            enzymes=["EcoRI", "BamHI"],
            require_all=True,
        ),
        assembly_overrides=AssemblySimulationConfig(
            strategy="gibson",
            base_success=0.75,
            tm_penalty_factor=0.08,
            minimal_site_count=1,
            low_site_penalty=0.7,
            ligation_efficiency=0.82,
            kinetics_model="isothermal_exonuclease",
            overlap_optimum=18,
            overlap_tolerance=4,
        ),
        metadata_tags=["preset:qpcr", "workflow:validation"],
        recommended_use=[
            "Assay verification",
            "qPCR target validation",
        ],
        notes=["Supports tight tm spreads suited to qPCR melt curve validation."],
    ),
    SequenceToolkitPreset(
        preset_id="high_gc",
        name="High-GC amplicons",
        description="Balances tm and clamps for GC-rich templates and Gibson workflows.",
        primer_overrides=PrimerDesignConfig(
            product_size_range=(140, 320),
            target_tm=64.0,
            min_tm=62.0,
            max_tm=68.0,
            min_size=22,
            opt_size=26,
            max_size=32,
            num_return=2,
            primer_concentration_nM=900.0,
            na_concentration_mM=70.0,
            gc_clamp_min=2,
            gc_clamp_max=4,
        ),
        restriction_overrides=RestrictionDigestConfig(
            enzymes=["NheI", "XhoI", "NotI"],
            require_all=False,
            reaction_buffer="High-GC",
        ),
        assembly_overrides=AssemblySimulationConfig(
            strategy="gibson",
            base_success=0.72,
            tm_penalty_factor=0.07,
            minimal_site_count=2,
            low_site_penalty=0.6,
            ligation_efficiency=0.9,
            kinetics_model="high_fidelity",
            overlap_optimum=28,
            overlap_tolerance=8,
        ),
        metadata_tags=["preset:high_gc", "workflow:gc_rich"],
        recommended_use=["GC-rich amplicon cloning", "Difficult template rescue"],
        notes=[
            "Increases clamp length and salt concentrations to stabilise GC-heavy primers.",
        ],
    ),
)


@lru_cache(maxsize=1)
def get_sequence_toolkit_presets() -> dict[str, SequenceToolkitPreset]:
    """Return indexed catalog of toolkit presets."""

    # purpose: allow deterministic preset lookups for planner orchestration
    return {entry.preset_id.lower(): entry for entry in _PRESET_DEFINITIONS}


def build_strategy_recommendations(
    template_sequences: Sequence[dict[str, Any]],
    *,
    preset_id: str | None = None,
    primer_payload: dict[str, Any] | None = None,
    restriction_payload: dict[str, Any] | None = None,
    assembly_payload: dict[str, Any] | None = None,
    qc_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a scored strategy bundle for toolkit presets."""

    # purpose: expose aggregated strategy scoring for planner and DNA viewer flows
    # inputs: template descriptors plus optional precomputed stage payloads
    # outputs: dict containing profile metadata, stage previews, and scorecards
    provided_profile: dict[str, Any] | None = None
    for payload in (primer_payload, restriction_payload, assembly_payload, qc_payload):
        if payload and isinstance(payload.get("profile"), dict):
            provided_profile = payload["profile"]
            break
    base_profile = SequenceToolkitProfile()
    if provided_profile:
        try:
            base_profile = SequenceToolkitProfile(**provided_profile)
        except Exception:  # pragma: no cover - defensive parsing for legacy payloads
            base_profile = SequenceToolkitProfile()
    resolved_profile = _resolve_profile(base_profile, preset_id=preset_id)
    target_preset = resolved_profile.preset_id or preset_id

    primer_result = primer_payload or design_primers(
        template_sequences,
        config=resolved_profile,
        preset_id=target_preset,
    )
    restriction_result = restriction_payload or analyze_restriction_digest(
        template_sequences,
        config=resolved_profile,
        preset_id=target_preset,
    )
    assembly_result = assembly_payload or simulate_assembly(
        primer_result,
        restriction_result,
        config=resolved_profile,
        strategy=(assembly_payload or {}).get("strategy")
        or resolved_profile.assembly.strategy,
        preset_id=target_preset,
    )
    qc_result = qc_payload or evaluate_qc_reports(
        assembly_result,
        config=resolved_profile,
    )

    primer_summary = (primer_result.get("summary") or {}).copy()
    primer_window = {
        "min_tm": primer_summary.get("min_tm"),
        "max_tm": primer_summary.get("max_tm"),
        "target_tm": (primer_result.get("profile") or {}).get("primer", {}).get("target_tm"),
    }
    tm_span = None
    if primer_window["min_tm"] is not None and primer_window["max_tm"] is not None:
        tm_span = round(primer_window["max_tm"] - primer_window["min_tm"], 3)

    strategy_scores: list[dict[str, Any]] = list(
        restriction_result.get("strategy_scores", [])
    )
    best_strategy = None
    compatibility_index = None
    if strategy_scores:
        sorted_scores = sorted(
            strategy_scores,
            key=lambda entry: entry.get("compatibility", 0.0),
            reverse=True,
        )
        best_strategy = sorted_scores[0]
        compatibility_index = round(
            sum(entry.get("compatibility", 0.0) for entry in sorted_scores[:3])
            / min(3, len(sorted_scores)),
            3,
        )

    qc_reports = qc_result.get("reports", []) if isinstance(qc_result, dict) else []
    qc_pass = sum(1 for report in qc_reports if report.get("status") == "pass")
    qc_rate = None
    if qc_reports:
        qc_rate = round(qc_pass / len(qc_reports), 3)

    preset_ref = (
        (primer_result.get("profile") or {}).get("preset_id")
        or target_preset
        or resolved_profile.preset_id
        or "default"
    )
    scorecard = {
        "preset_id": preset_ref,
        "preset_name": (primer_result.get("profile") or {}).get("preset_name"),
        "primer_window": primer_window,
        "tm_span": tm_span,
        "primer_count": primer_summary.get("primer_count"),
        "multiplex_risk": (primer_result.get("multiplex") or {}).get("risk_level"),
        "best_strategy": (best_strategy or {}).get("strategy"),
        "best_strategy_score": (best_strategy or {}).get("compatibility"),
        "recommended_buffers": (best_strategy or {}).get("buffer_recommendations", []),
        "compatibility_index": compatibility_index,
        "assembly_success": assembly_result.get("average_success"),
        "qc_pass_rate": qc_rate,
    }

    profile_dump = (
        (primer_result.get("profile") or {})
        or (restriction_result.get("profile") or {})
        or resolved_profile.model_dump()
    )
    recommendations = {
        "profile": profile_dump,
        "primer": primer_result,
        "restriction": restriction_result,
        "assembly": assembly_result,
        "qc": qc_result,
        "scorecard": scorecard,
        "strategy_scores": strategy_scores,
    }
    return recommendations


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


def _max_cross_dimer_run(seq_a: str, seq_b: str) -> int:
    """Return the maximum complement run between two primers."""

    # purpose: assess multiplex cross-dimer overlap heuristics
    primer_a = _normalize_sequence(seq_a)
    primer_b = _reverse_complement(seq_b)
    max_run = 0
    for idx in range(len(primer_a)):
        for jdx in range(len(primer_b)):
            run = 0
            while (
                idx + run < len(primer_a)
                and jdx + run < len(primer_b)
                and primer_a[idx + run] == primer_b[jdx + run]
            ):
                run += 1
            if run > max_run:
                max_run = run
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


@lru_cache(maxsize=1)
def get_enzyme_kinetics() -> list[EnzymeKineticsProfile]:
    """Return curated enzyme kinetics descriptors."""

    # purpose: expose kinetics parameters for assembly scoring reuse
    return [
        EnzymeKineticsProfile(**entry) for entry in get_enzyme_kinetics_catalog()
    ]


@lru_cache(maxsize=1)
def get_ligation_profiles() -> list[LigationEfficiencyProfile]:
    """Return ligation efficiency presets."""

    # purpose: align ligation heuristics for planners and DNA assets
    return [
        LigationEfficiencyProfile(**entry)
        for entry in get_ligation_profile_catalog()
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


def _enzyme_kinetics_index() -> dict[str, EnzymeKineticsProfile]:
    """Return kinetics descriptors keyed by normalized enzyme name."""

    # purpose: accelerate kinetics lookups for digest and assembly heuristics
    return {record.name.lower(): record for record in get_enzyme_kinetics()}


def _ligation_profile_index() -> dict[tuple[str, str | None], LigationEfficiencyProfile]:
    """Return ligation efficiency presets keyed by strategy and enzyme."""

    # purpose: enable quick ligation preset matching during assembly scoring
    index: dict[tuple[str, str | None], LigationEfficiencyProfile] = {}
    for profile in get_ligation_profiles():
        key = (profile.strategy.lower(), (profile.enzyme or "").lower() or None)
        index[key] = profile
    return index


def _resolve_ligation_profile(
    strategy: str | None, enzyme_names: Sequence[str], buffer_name: str | None
) -> LigationEfficiencyProfile | None:
    """Return matching ligation profile for the provided context."""

    # purpose: centralize ligation profile lookups for deterministic scoring
    strategy_key = (strategy or "unspecified").lower()
    profile_index = _ligation_profile_index()
    matched_profile: LigationEfficiencyProfile | None = None
    normalized_buffer = (buffer_name or "").lower() or None
    for enzyme in enzyme_names:
        key = (strategy_key, enzyme.lower())
        profile = profile_index.get(key)
        if not profile:
            continue
        matched_profile = profile
        profile_buffer = (profile.buffer or "").lower() or None
        if not profile_buffer or normalized_buffer == profile_buffer:
            return profile
    if not matched_profile:
        matched_profile = profile_index.get((strategy_key, None))
    return matched_profile


def _kinetics_modifier(
    kinetics_model: str,
    tm_delta: float,
    site_count: int,
    heuristics: dict[str, Any],
    kinetics_profile: EnzymeKineticsProfile | None = None,
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
    if kinetics_profile and kinetics_profile.model:
        heuristics["kinetics_profile_model"] = kinetics_profile.model
    if kinetics_profile and kinetics_profile.rate_constant:
        heuristics["kinetics_rate_constant"] = kinetics_profile.rate_constant
        base *= min(1.05, max(0.6, kinetics_profile.rate_constant))
    if kinetics_profile and kinetics_profile.optimal_temperature_c:
        heuristics["kinetics_opt_temp_c"] = kinetics_profile.optimal_temperature_c
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


def _evaluate_restriction_strategies(
    digests: Sequence[RestrictionDigestResult],
    *,
    profile: SequenceToolkitProfile,
    default_buffer: ReactionBuffer | None,
) -> list[RestrictionStrategyEvaluation]:
    """Return strategy compatibility evaluations for restriction digests."""

    # purpose: surface double digest and Golden Gate readiness for planner guardrails
    total = len(digests)
    if not total:
        return []
    double_ready = 0
    partial_ready = 0
    buffer_recommendations: set[str] = set()
    if default_buffer and default_buffer.name:
        buffer_recommendations.add(default_buffer.name)
    golden_scores: list[float] = []
    type_iis_names = {
        "bsai",
        "bsmbi",
        "bsmbi-v2",
        "sapI".lower(),
        "bbsi",
        "esp3i",
    }
    for digest in digests:
        enzyme_hits = 0
        type_iis_hit = 0
        overhang_signatures: set[str] = set()
        buffer_payload = digest.buffer
        if buffer_payload:
            if isinstance(buffer_payload, ReactionBuffer):
                if buffer_payload.name:
                    buffer_recommendations.add(buffer_payload.name)
            elif isinstance(buffer_payload, dict):
                buffer_name = buffer_payload.get("name")
                if buffer_name:
                    buffer_recommendations.add(buffer_name)
        for site in digest.sites.values():
            positions = site.positions if isinstance(site, RestrictionDigestSite) else []
            if positions:
                enzyme_hits += 1
            enzyme_name = (site.enzyme or "").lower()
            if enzyme_name in type_iis_names and positions:
                type_iis_hit += len(positions)
                metadata = site.metadata
                overhang = None
                if isinstance(metadata, EnzymeMetadata):
                    overhang = metadata.overhang or metadata.recognition_site
                elif isinstance(metadata, dict):
                    overhang = metadata.get("overhang") or metadata.get("recognition_site")
                if overhang:
                    overhang_signatures.add(str(overhang))
        if enzyme_hits >= 2:
            double_ready += 1
        elif enzyme_hits == 1:
            partial_ready += 1
        if type_iis_hit >= 2 and len(overhang_signatures) >= 2:
            golden_scores.append(1.0)
        elif type_iis_hit >= 1:
            golden_scores.append(0.5)
        else:
            golden_scores.append(0.0)
    double_score = (
        (double_ready + (partial_ready * 0.5)) / total if total else 0.0
    )
    double_hint = "Double digest ready for execution" if double_score >= 0.75 else (
        "Double digest requires enzyme balancing" if double_score >= 0.4 else "Double digest blocked: insufficient cut site coverage"
    )
    double_metadata = sorted(
        {
            *profile.metadata_tags,
            "strategy:double_digest",
        }
    )
    double_notes: list[str] = []
    if double_score < 0.75:
        double_notes.append(
            "Ensure at least two enzymes cut each template to sustain parallel digests."
        )
    if partial_ready:
        double_notes.append(
            f"{partial_ready} template(s) only have a single enzyme with cut sites."
        )
    if profile.preset_id:
        double_notes.append(
            f"Preset {profile.preset_id} applied to restriction scoring."
        )
    evaluations = [
        RestrictionStrategyEvaluation(
            strategy="double_digest",
            compatibility=round(double_score, 3),
            buffer_recommendations=sorted(buffer_recommendations),
            guardrail_hint=double_hint,
            notes=double_notes,
            metadata_tags=double_metadata,
        )
    ]
    golden_score = mean(golden_scores) if golden_scores else 0.0
    golden_hint = "Golden Gate ready for multiplex assembly" if golden_score >= 0.75 else (
        "Golden Gate requires overhang diversification" if golden_score >= 0.4 else "Golden Gate blocked: insufficient Type IIS coverage"
    )
    golden_notes: list[str] = []
    if golden_score < 0.75:
        golden_notes.append(
            "Increase Type IIS site count and diversify overhangs for Golden Gate."
        )
    if profile.recommended_use:
        golden_notes.extend(profile.recommended_use)
    golden_metadata = sorted(
        {
            *profile.metadata_tags,
            "strategy:golden_gate",
        }
    )
    evaluations.append(
        RestrictionStrategyEvaluation(
            strategy="golden_gate",
            compatibility=round(golden_score, 3),
            buffer_recommendations=sorted(buffer_recommendations),
            guardrail_hint=golden_hint,
            notes=golden_notes,
            metadata_tags=golden_metadata,
        )
    )
    return evaluations


def _resolve_profile(
    config: PrimerDesignConfig
    | RestrictionDigestConfig
    | AssemblySimulationConfig
    | SequenceToolkitProfile
    | QCConfig
    | None,
    *,
    preset_id: str | None = None,
) -> SequenceToolkitProfile:
    """Return a SequenceToolkitProfile with optional preset overrides applied."""

    # purpose: centralize preset application for primer, restriction, and assembly flows
    if isinstance(config, SequenceToolkitProfile):
        base_profile = SequenceToolkitProfile(**config.model_dump())
    elif isinstance(config, PrimerDesignConfig):
        base_profile = SequenceToolkitProfile(primer=config)
    elif isinstance(config, RestrictionDigestConfig):
        base_profile = SequenceToolkitProfile(restriction=config)
    elif isinstance(config, AssemblySimulationConfig):
        base_profile = SequenceToolkitProfile(assembly=config)
    elif isinstance(config, QCConfig):
        base_profile = SequenceToolkitProfile(qc=config)
    else:
        base_profile = SequenceToolkitProfile()
    selected = (preset_id or base_profile.preset_id or "").lower()
    if not selected:
        return base_profile
    preset_catalog = get_sequence_toolkit_presets()
    preset = preset_catalog.get(selected)
    if not preset:
        return base_profile
    primer = base_profile.primer.model_copy()
    if preset.primer_overrides:
        primer = primer.model_copy(
            update=preset.primer_overrides.model_dump()
        )
    restriction = base_profile.restriction.model_copy()
    if preset.restriction_overrides:
        restriction = restriction.model_copy(
            update=preset.restriction_overrides.model_dump()
        )
    assembly = base_profile.assembly.model_copy()
    if preset.assembly_overrides:
        assembly = assembly.model_copy(
            update=preset.assembly_overrides.model_dump()
        )
    metadata_tags = sorted(
        {
            *base_profile.metadata_tags,
            *preset.metadata_tags,
            f"preset:{preset.preset_id}",
        }
    )
    recommended_use = sorted(
        set((*base_profile.recommended_use, *preset.recommended_use))
    )
    notes = list(dict.fromkeys([*base_profile.notes, *preset.notes]))
    return SequenceToolkitProfile(
        preset_id=preset.preset_id,
        preset_name=preset.name,
        preset_description=preset.description,
        metadata_tags=metadata_tags,
        primer=primer,
        restriction=restriction,
        assembly=assembly,
        qc=base_profile.qc.model_copy(),
        recommended_use=recommended_use,
        notes=notes,
    )


def _resolve_primer_config(
    config: PrimerDesignConfig | SequenceToolkitProfile | None,
    *,
    product_size_range: tuple[int, int] | None,
    target_tm: float | None,
    preset_id: str | None = None,
) -> tuple[SequenceToolkitProfile, PrimerDesignConfig, tuple[int, int], float]:
    profile = _resolve_profile(config, preset_id=preset_id)
    primer_config = profile.primer.model_copy()
    size_range = product_size_range or primer_config.product_size_range
    tm_request = target_tm if target_tm is not None else primer_config.target_tm
    clamped_tm = max(primer_config.min_tm, min(primer_config.max_tm, tm_request))
    primer_config = primer_config.model_copy(update={"target_tm": clamped_tm})
    profile = profile.model_copy(update={"primer": primer_config})
    return profile, primer_config, size_range, clamped_tm


def _resolve_restriction_config(
    config: RestrictionDigestConfig | SequenceToolkitProfile | None,
    *,
    enzymes: Sequence[str] | None,
    preset_id: str | None = None,
) -> tuple[SequenceToolkitProfile, RestrictionDigestConfig]:
    profile = _resolve_profile(config, preset_id=preset_id)
    base = profile.restriction.model_copy()
    if enzymes:
        base = base.model_copy(update={"enzymes": list(enzymes)})
    profile = profile.model_copy(update={"restriction": base})
    return profile, base


def _resolve_assembly_config(
    config: AssemblySimulationConfig | SequenceToolkitProfile | None,
    *,
    strategy: str | None,
    preset_id: str | None = None,
) -> tuple[SequenceToolkitProfile, AssemblySimulationConfig]:
    profile = _resolve_profile(config, preset_id=preset_id)
    base = profile.assembly.model_copy()
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
    profile = profile.model_copy(update={"assembly": base})
    return profile, base


def _resolve_qc_config(
    config: QCConfig | SequenceToolkitProfile | None,
    *,
    preset_id: str | None = None,
) -> tuple[SequenceToolkitProfile, QCConfig]:
    profile = _resolve_profile(config, preset_id=preset_id)
    return profile, profile.qc.model_copy()


def design_primers(
    template_sequences: Sequence[dict[str, Any]],
    *,
    config: PrimerDesignConfig | SequenceToolkitProfile | None = None,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    preset_id: str | None = None,
) -> dict[str, Any]:
    """Generate primer sets for uploaded templates using Primer3."""

    # purpose: derive thermodynamically-validated primers for planner stages
    # inputs: sequence descriptors with `name` and `sequence` keys
    # outputs: mapping of template names to primer metrics compatible with planner schemas
    # status: experimental
    profile, primer_config, size_range, tm_target = _resolve_primer_config(
        config,
        product_size_range=product_size_range,
        target_tm=target_tm,
        preset_id=preset_id,
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
        metadata_tags: list[str] = [f"primer_source:{primer_source}"]
        if primer_source == "fallback":
            notes.append("Primer3 returned no candidates; deterministic fallback used.")
            metadata_tags.append("primer_source:fallback")
        tm_delta = abs(forward.tm - reverse.tm)
        if tm_delta > 2.0:
            warnings.append(f"Primer Tm delta {tm_delta:.2f} exceeds tolerance")
            metadata_tags.append("warning:tm_delta_high")
        gc_delta = abs(forward.gc_content - reverse.gc_content)
        if gc_delta > 10:
            warnings.append(f"Primer GC delta {gc_delta:.2f} exceeds tolerance")
            metadata_tags.append("warning:gc_delta_high")
        forward_clamp = sum(
            1 for base in forward.sequence[-primer_config.gc_clamp_max :] if base in {"G", "C"}
        )
        reverse_clamp = sum(
            1 for base in reverse.sequence[-primer_config.gc_clamp_max :] if base in {"G", "C"}
        )
        if forward_clamp < primer_config.gc_clamp_min or reverse_clamp < primer_config.gc_clamp_min:
            warnings.append("GC clamp below configured minimum")
            metadata_tags.append("warning:gc_clamp_low")
        if forward.hairpin_delta_g and forward.hairpin_delta_g < -6:
            warnings.append(
                f"Forward primer predicted hairpin ΔG {forward.hairpin_delta_g:.2f} kcal/mol"
            )
            metadata_tags.append("risk:hairpin_forward")
        if reverse.hairpin_delta_g and reverse.hairpin_delta_g < -6:
            warnings.append(
                f"Reverse primer predicted hairpin ΔG {reverse.hairpin_delta_g:.2f} kcal/mol"
            )
            metadata_tags.append("risk:hairpin_reverse")
        if forward.homodimer_delta_g and forward.homodimer_delta_g < -6:
            warnings.append(
                f"Forward primer homodimer ΔG {forward.homodimer_delta_g:.2f} kcal/mol"
            )
            metadata_tags.append("risk:homodimer_forward")
        if reverse.homodimer_delta_g and reverse.homodimer_delta_g < -6:
            warnings.append(
                f"Reverse primer homodimer ΔG {reverse.homodimer_delta_g:.2f} kcal/mol"
            )
            metadata_tags.append("risk:homodimer_reverse")
        if warnings:
            metadata_tags.append("primer_warning:present")
        if profile.metadata_tags:
            metadata_tags.extend(profile.metadata_tags)
        if profile.preset_id:
            metadata_tags.append(f"preset:{profile.preset_id}")
        records.append(
            PrimerDesignRecord(
                name=name,
                status="ok",
                forward=_primer_candidate_from_result(forward),
                reverse=_primer_candidate_from_result(reverse),
                product_size=product_size,
                warnings=warnings,
                metadata_tags=sorted(set(metadata_tags)),
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
    primer_pairs: list[tuple[str, PrimerCandidate]] = []
    for record in records:
        if record.forward:
            primer_pairs.append((f"{record.name}:forward", record.forward))
        if record.reverse:
            primer_pairs.append((f"{record.name}:reverse", record.reverse))
    cross_dimer_flags: list[PrimerCrossDimerFlag] = []
    for idx in range(len(primer_pairs)):
        name_a, primer_a = primer_pairs[idx]
        for jdx in range(idx + 1, len(primer_pairs)):
            name_b, primer_b = primer_pairs[jdx]
            overlap = _max_cross_dimer_run(primer_a.sequence, primer_b.sequence)
            if overlap < 5:
                continue
            delta_g = _delta_g_from_run(overlap)
            severity = "blocked" if overlap >= 7 else "review"
            flag_tags = [f"overlap:{overlap}"]
            if profile.preset_id:
                flag_tags.append(f"preset:{profile.preset_id}")
            cross_dimer_flags.append(
                PrimerCrossDimerFlag(
                    primer_a=name_a,
                    primer_b=name_b,
                    overlap=overlap,
                    delta_g=delta_g,
                    severity=severity,
                    metadata_tags=flag_tags,
                    notes=[
                        (
                            "Predicted cross-dimer overlap "
                            f"of {overlap} bases between {name_a} and {name_b}"
                        )
                    ],
                )
            )
    delta_tm_window = summary.max_tm - summary.min_tm if tm_values else 0.0
    risk_level = "ok"
    multiplex_notes = list(profile.notes)
    if delta_tm_window > 6.0:
        risk_level = "blocked"
        multiplex_notes.append(
            "Tm window exceeds 6°C; multiplex runs require redesign or staging."
        )
    elif delta_tm_window > 4.0:
        risk_level = "review"
        multiplex_notes.append(
            "Tm window exceeds 4°C; balance primer pairs before multiplexing."
        )
    if any(flag.severity == "blocked" for flag in cross_dimer_flags):
        risk_level = "blocked"
    elif risk_level != "blocked" and any(
        flag.severity == "review" for flag in cross_dimer_flags
    ):
        risk_level = "review"
    if cross_dimer_flags and all(
        "cross_dimer" not in tag for tag in profile.metadata_tags
    ):
        multiplex_notes.append("Cross-dimer risk detected across multiplex primer sets.")
    multiplex_metadata = sorted(
        {
            *profile.metadata_tags,
            "assessment:multiplex",
            *(flag.metadata_tags[0] for flag in cross_dimer_flags if flag.metadata_tags),
        }
    )
    multiplex = PrimerMultiplexCompatibility(
        risk_level=risk_level,
        delta_tm_window=delta_tm_window,
        average_tm=summary.average_tm,
        cross_dimer_flags=cross_dimer_flags,
        metadata_tags=multiplex_metadata,
        recommended_use=profile.recommended_use,
        notes=multiplex_notes,
    )
    response = PrimerDesignResponse(
        primers=records,
        summary=summary,
        multiplex=multiplex,
    )
    payload = response.model_dump()
    payload["profile"] = profile.model_dump()
    return payload


def analyze_restriction_digest(
    template_sequences: Sequence[dict[str, Any]],
    *,
    config: RestrictionDigestConfig | SequenceToolkitProfile | None = None,
    enzymes: Sequence[str] | None = None,
    preset_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate restriction sites for templates."""

    # purpose: provide enzyme compatibility scoring for planner assembly strategies
    # inputs: sequence descriptors and optional enzyme list
    # outputs: digest summary keyed by template
    # status: experimental
    profile, digest_config = _resolve_restriction_config(
        config,
        enzymes=enzymes,
        preset_id=preset_id,
    )
    enzyme_list = list(digest_config.enzymes)
    catalog_index = _enzyme_index()
    kinetics_index = _enzyme_kinetics_index()
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
        template_tags: list[str] = []
        for enzyme_name, positions in site_map.items():
            meta = catalog_index.get(enzyme_name.lower())
            kinetics = kinetics_index.get(enzyme_name.lower())
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
                kinetics=kinetics,
            )
            if meta and meta.metadata_tags:
                template_tags.extend(tag for tag in meta.metadata_tags if tag not in template_tags)
            if kinetics and kinetics.metadata_tags:
                template_tags.extend(
                    tag for tag in kinetics.metadata_tags if tag not in template_tags
                )
        if profile.metadata_tags:
            template_tags.extend(
                tag for tag in profile.metadata_tags if tag not in template_tags
            )
        if profile.preset_id:
            template_tags.append(f"preset:{profile.preset_id}")
        digest_notes: list[str] = []
        for enzyme_name, meta in ((entry.name, entry) for entry in enzyme_catalog):
            if meta.star_activity_notes:
                digest_notes.append(f"{enzyme_name}: {meta.star_activity_notes}")
        if selected_buffer:
            digest_notes.append(
                f"Buffer {selected_buffer.name}: {selected_buffer.notes or 'no notes recorded.'}"
            )
            template_tags.extend(
                tag
                for tag in (selected_buffer.metadata_tags or [])
                if tag not in template_tags
            )
        seen_kinetics: set[str] = set()
        kinetics_profiles: list[EnzymeKineticsProfile] = []
        for site in site_payload.values():
            kinetics_entry = site.kinetics
            if not kinetics_entry:
                continue
            key = kinetics_entry.name.lower() if kinetics_entry.name else None
            if key and key not in seen_kinetics:
                kinetics_profiles.append(kinetics_entry)
                seen_kinetics.add(key)
        digest_results.append(
            RestrictionDigestResult(
                name=name,
                sites=site_payload,
                compatible=compatible,
                buffer_alerts=buffer_alerts,
                notes=digest_notes,
                buffer=selected_buffer,
                metadata_tags=sorted(template_tags),
                kinetics_profiles=kinetics_profiles,
            )
        )
        absent_enzymes = [enz for enz, positions in site_map.items() if not positions]
        if absent_enzymes:
            compatibility_alerts.append(
                f"{name} lacks cut sites for {', '.join(absent_enzymes)}"
            )
    strategy_scores = _evaluate_restriction_strategies(
        digest_results,
        profile=profile,
        default_buffer=selected_buffer,
    )
    response = RestrictionDigestResponse(
        enzymes=enzyme_catalog,
        digests=digest_results,
        alerts=compatibility_alerts + metadata_alerts,
        strategy_scores=strategy_scores,
    )
    payload = response.model_dump()
    payload["profile"] = profile.model_dump()
    return payload


def simulate_assembly(
    primer_results: dict[str, Any],
    digest_results: dict[str, Any],
    *,
    config: AssemblySimulationConfig | SequenceToolkitProfile | None = None,
    strategy: str | None = None,
    preset_id: str | None = None,
) -> dict[str, Any]:
    """Generate assembly plan heuristics."""

    # purpose: estimate assembly junction success probabilities for planner guardrails
    # inputs: primer and restriction digest outputs with selected strategy
    # outputs: plan structure containing steps and success scoring
    # status: experimental
    profile, assembly_config = _resolve_assembly_config(
        config,
        strategy=strategy,
        preset_id=preset_id,
    )
    steps: list[AssemblyStepMetrics] = []
    success_scores: list[float] = []
    primers = primer_results.get("primers", [])
    digests = {
        item["name"]: item for item in digest_results.get("digests", [])
    }
    contract_tags: set[str] = {f"strategy:{assembly_config.strategy}"}
    contract_tags.update(profile.metadata_tags)
    kinetics_index = _enzyme_kinetics_index()
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
        enzyme_names: list[str] = []
        step_kinetics_profiles: list[EnzymeKineticsProfile] = []
        seen_step_kinetics: set[str] = set()
        step_tags: set[str] = set(digest.get("metadata_tags", []))
        for enzyme_key, site in (digest.get("sites", {}) or {}).items():
            if isinstance(site, dict):
                site_positions = site.get("positions", [])
            else:
                site_positions = site
            site_count += len(site_positions)
            if isinstance(site, dict):
                enzyme_name = site.get("enzyme") or enzyme_key
                if enzyme_name:
                    enzyme_names.append(enzyme_name)
                site_meta = site.get("metadata") or {}
                overhang = site_meta.get("overhang") or site_meta.get("recognition_site")
                if overhang:
                    overhang_signatures.add(str(overhang))
                kinetics_payload = site.get("kinetics")
                if kinetics_payload:
                    if isinstance(kinetics_payload, dict):
                        metadata_tags = kinetics_payload.get("metadata_tags", [])
                        if metadata_tags:
                            step_tags.update(metadata_tags)
                        kinetics_name = (kinetics_payload.get("name") or "").lower()
                        if kinetics_name and kinetics_name not in seen_step_kinetics:
                            step_kinetics_profiles.append(EnzymeKineticsProfile(**kinetics_payload))
                            seen_step_kinetics.add(kinetics_name)
                    else:
                        if kinetics_payload.metadata_tags:
                            step_tags.update(kinetics_payload.metadata_tags)
                        kinetics_name = (kinetics_payload.name or "").lower()
                        if kinetics_name and kinetics_name not in seen_step_kinetics:
                            step_kinetics_profiles.append(kinetics_payload)
                            seen_step_kinetics.add(kinetics_name)
        overhang_diversity = len(overhang_signatures) or site_count
        enzyme_names = list(dict.fromkeys(enzyme_names))
        buffer_penalty = 0.0
        if digest.get("buffer_alerts"):
            buffer_penalty += min(0.3, 0.05 * len(digest["buffer_alerts"]))
        raw_buffer = digest.get("buffer")
        if isinstance(raw_buffer, ReactionBuffer):
            buffer_obj = raw_buffer
            buffer_meta = raw_buffer.model_dump()
        elif isinstance(raw_buffer, dict):
            buffer_meta = raw_buffer
            buffer_obj = ReactionBuffer(**raw_buffer) if raw_buffer else None
        else:
            buffer_meta = {}
            buffer_obj = None
        if buffer_obj and buffer_obj.metadata_tags:
            step_tags.update(buffer_obj.metadata_tags)
        compatible_strategies = buffer_meta.get("compatible_strategies", [])
        buffer_name = buffer_obj.name if buffer_obj else buffer_meta.get("name")
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
        ligation_profile = _resolve_ligation_profile(
            assembly_config.strategy,
            enzyme_names,
            buffer_name,
        )
        ligation_efficiency = assembly_config.ligation_efficiency
        if ligation_profile:
            heuristics["ligation_profile"] = {
                "strategy": ligation_profile.strategy,
                "enzyme": ligation_profile.enzyme,
                "efficiency_ceiling": ligation_profile.efficiency_ceiling,
                "buffer": ligation_profile.buffer,
            }
            ligation_efficiency = max(
                ligation_efficiency,
                ligation_profile.base_efficiency,
            )
            ligation_efficiency = min(
                ligation_efficiency,
                ligation_profile.efficiency_ceiling,
            )
            step_tags.update(ligation_profile.metadata_tags)
        kinetics_profile = step_kinetics_profiles[0] if step_kinetics_profiles else None
        if kinetics_profile is None:
            for enzyme_name in enzyme_names:
                candidate = kinetics_index.get(enzyme_name.lower())
                if candidate:
                    kinetics_profile = candidate
                    break
        if kinetics_profile:
            if kinetics_profile.metadata_tags:
                step_tags.update(kinetics_profile.metadata_tags)
            kinetics_name = (kinetics_profile.name or "").lower()
            if kinetics_name and kinetics_name not in seen_step_kinetics:
                step_kinetics_profiles.append(kinetics_profile)
                seen_step_kinetics.add(kinetics_name)
        score *= ligation_efficiency
        kinetics_score = _kinetics_modifier(
            assembly_config.kinetics_model,
            tm_delta,
            site_count,
            heuristics,
            kinetics_profile,
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
        if ligation_profile and ligation_profile.base_efficiency < 0.8:
            warnings.append("Ligation preset below optimal efficiency")
        step_tags.update(entry.get("metadata_tags", []))
        metadata_tags = sorted(step_tags)
        contract_tags.update(metadata_tags)
        steps.append(
            AssemblyStepMetrics(
                template=name,
                strategy=assembly_config.strategy,
                expected_fragment_count=max(1, site_count),
                junction_success=score,
                ligation_efficiency=ligation_efficiency,
                kinetics_score=kinetics_score,
                ligation_profile=ligation_profile,
                buffer=buffer_obj,
                kinetics_profiles=step_kinetics_profiles,
                heuristics=heuristics,
                warnings=warnings,
                metadata_tags=metadata_tags,
            )
        )
    aggregated_tags = sorted(contract_tags)
    payload_contract = {
        "schema_version": "1.1",
        "strategy": assembly_config.strategy,
        "metadata_tags": aggregated_tags,
        "fields": [
            "strategy",
            "steps",
            "average_success",
            "min_success",
            "max_success",
            "payload_contract",
        ],
    }
    result = AssemblySimulationResult(
        strategy=assembly_config.strategy,
        steps=steps,
        average_success=mean(success_scores) if success_scores else 0.0,
        min_success=min(success_scores) if success_scores else 0.0,
        max_success=max(success_scores) if success_scores else 0.0,
        payload_contract=payload_contract,
        metadata_tags=aggregated_tags,
    ).model_dump()
    result["profile"] = profile.model_dump()
    return result


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
    profile, qc_config = _resolve_qc_config(config)
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
    response = QCReportResponse(reports=reports).model_dump()
    response["profile"] = profile.model_dump()
    return response
