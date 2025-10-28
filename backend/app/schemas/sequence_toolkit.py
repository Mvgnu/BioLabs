"""Configuration schemas for sequence toolkit operations."""

# purpose: capture scientific configuration profiles for shared sequence computations
# status: experimental
# related_docs: docs/dna_assets.md

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class PrimerDesignConfig(BaseModel):
    """Primer design configuration options shared across planners and DNA assets."""

    # purpose: define thermodynamic and sizing constraints for primer3 execution
    product_size_range: Tuple[int, int] = (80, 280)
    target_tm: float = Field(default=60.0, ge=0.0)
    min_tm: float = Field(default=55.0, ge=0.0)
    max_tm: float = Field(default=65.0, ge=0.0)
    min_size: int = Field(default=18, ge=12)
    opt_size: int = Field(default=22, ge=12)
    max_size: int = Field(default=30, ge=12)
    num_return: int = Field(default=1, ge=1)
    na_concentration_mM: float = Field(default=50.0, ge=0.0)
    primer_concentration_nM: float = Field(default=500.0, ge=0.0)
    gc_clamp_min: int = Field(default=1, ge=0)
    gc_clamp_max: int = Field(default=2, ge=0)


class RestrictionDigestConfig(BaseModel):
    """Restriction digest heuristic configuration."""

    # purpose: specify enzyme catalog defaults and compatibility heuristics
    enzymes: List[str] = Field(
        default_factory=lambda: ["EcoRI", "BamHI", "BsaI", "BsmBI"],
    )
    require_all: bool = True
    reaction_buffer: Optional[str] = None


class ReactionBuffer(BaseModel):
    """Reaction buffer metadata for restriction digests and assemblies."""

    # purpose: document buffer compositions and compatibility
    name: str
    ionic_strength_mM: float
    ph: float
    stabilizers: List[str] = Field(default_factory=list)
    compatible_strategies: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    metadata_tags: List[str] = Field(default_factory=list)


class EnzymeKineticsProfile(BaseModel):
    """Structured kinetics descriptor for enzymes."""

    # purpose: expose kinetic parameters for digestion and assembly scoring
    name: str
    model: str
    optimal_temperature_c: Optional[float] = Field(default=None, ge=0.0)
    km_uM: Optional[float] = Field(default=None, ge=0.0)
    kcat_s: Optional[float] = Field(default=None, ge=0.0)
    rate_constant: Optional[float] = Field(default=None, ge=0.0)
    metadata_tags: List[str] = Field(default_factory=list)


class LigationEfficiencyProfile(BaseModel):
    """Reusable ligation efficiency descriptor."""

    # purpose: align ligation efficiency presets across services
    strategy: str
    enzyme: Optional[str] = None
    base_efficiency: float = Field(ge=0.0, le=1.0)
    efficiency_ceiling: float = Field(default=1.0, ge=0.0, le=1.0)
    buffer: Optional[str] = None
    metadata_tags: List[str] = Field(default_factory=list)


class AssemblyStrategyProfile(BaseModel):
    """Assembly strategy descriptor loaded from catalog data."""

    # purpose: provide reusable heuristics for simulation scoring
    name: str
    base_success: float = Field(ge=0.0, le=1.0)
    tm_penalty_factor: float = Field(ge=0.0)
    minimal_site_count: int = Field(ge=0)
    low_site_penalty: float = Field(ge=0.0, le=1.0)
    ligation_efficiency: float = Field(default=0.85, ge=0.0, le=1.0)
    kinetics_model: str = "unspecified"
    overlap_optimum: Optional[int] = Field(default=None, ge=0)
    overlap_tolerance: Optional[int] = Field(default=None, ge=0)
    overhang_diversity_factor: Optional[float] = Field(default=None, ge=0.0)


class AssemblySimulationConfig(BaseModel):
    """Assembly simulation parameters."""

    # purpose: configure assembly scoring heuristics for planner and DNA asset simulations
    strategy: str = "gibson"
    base_success: float = Field(default=0.85, ge=0.0, le=1.0)
    tm_penalty_factor: float = Field(default=0.1, ge=0.0)
    minimal_site_count: int = Field(default=2, ge=0)
    low_site_penalty: float = Field(default=0.4, ge=0.0, le=1.0)
    ligation_efficiency: float = Field(default=0.85, ge=0.0, le=1.0)
    kinetics_model: str = "unspecified"
    overlap_optimum: Optional[int] = Field(default=None, ge=0)
    overlap_tolerance: Optional[int] = Field(default=None, ge=0)
    overhang_diversity_factor: Optional[float] = Field(default=None, ge=0.0)


class QCConfig(BaseModel):
    """Quality control acceptance configuration."""

    # purpose: define pass/review thresholds for assembly and chromatogram QC
    junction_pass_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    chromatogram_mismatch_threshold: float = Field(default=0.05, ge=0.0, le=1.0)


class SequenceToolkitProfile(BaseModel):
    """Aggregate configuration bundle for sequence toolkit consumers."""

    # purpose: provide cohesive profile overrides for planner and DNA asset workflows
    primer: PrimerDesignConfig = Field(default_factory=PrimerDesignConfig)
    restriction: RestrictionDigestConfig = Field(default_factory=RestrictionDigestConfig)
    assembly: AssemblySimulationConfig = Field(default_factory=AssemblySimulationConfig)
    qc: QCConfig = Field(default_factory=QCConfig)

    def with_strategy(self, strategy: str) -> "SequenceToolkitProfile":
        """Return a cloned profile with the specified assembly strategy."""

        # purpose: allow quick derivation of per-strategy assembly heuristics
        return SequenceToolkitProfile(
            primer=self.primer.model_copy(),
            restriction=self.restriction.model_copy(),
            assembly=self.assembly.model_copy(update={"strategy": strategy}),
            qc=self.qc.model_copy(),
        )


class EnzymeMetadata(BaseModel):
    """Structured metadata for restriction enzymes."""

    # purpose: expose curated catalog attributes for downstream planning logic
    name: str
    recognition_site: str
    cut_pattern: Optional[str] = None
    overhang: Optional[str] = None
    optimal_temperature_c: Optional[float] = Field(default=None, ge=0.0)
    compatible_buffers: List[str] = Field(default_factory=list)
    methylation_sensitivity: Optional[str] = None
    star_activity_notes: Optional[str] = None
    supplier: Optional[str] = None
    metadata_tags: List[str] = Field(default_factory=list)


class RestrictionDigestSite(BaseModel):
    """Restriction digest site locations for a specific enzyme."""

    # purpose: communicate site counts and annotations per enzyme
    enzyme: str
    positions: List[int] = Field(default_factory=list)
    recognition_site: Optional[str] = None
    metadata: Optional[EnzymeMetadata] = None
    kinetics: Optional[EnzymeKineticsProfile] = None


class RestrictionDigestResult(BaseModel):
    """Digest compatibility summary for a template."""

    # purpose: report enzyme coverage and compatibility warnings to planners
    name: str
    sites: Dict[str, RestrictionDigestSite]
    compatible: bool
    buffer_alerts: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    buffer: Optional[ReactionBuffer] = None
    metadata_tags: List[str] = Field(default_factory=list)


class RestrictionDigestResponse(BaseModel):
    """Aggregate restriction digest response payload."""

    # purpose: standardize digest outputs for services and routes
    enzymes: List[EnzymeMetadata]
    digests: List[RestrictionDigestResult]
    alerts: List[str] = Field(default_factory=list)


class PrimerThermodynamics(BaseModel):
    """Thermodynamic features for primer candidates."""

    # purpose: capture melting temp and structure risk heuristics
    tm: float = Field(ge=0.0)
    gc_content: float = Field(ge=0.0, le=100.0)
    hairpin_delta_g: Optional[float] = None
    homodimer_delta_g: Optional[float] = None


class PrimerCandidate(BaseModel):
    """Primer candidate descriptor with contextual metrics."""

    # purpose: unify primer outputs across DNA asset and planner workflows
    sequence: str
    start: int
    length: int
    thermodynamics: PrimerThermodynamics


class PrimerDesignRecord(BaseModel):
    """Paired primer result for a template."""

    # purpose: express primer design outcome including warnings
    name: str
    status: str
    forward: Optional[PrimerCandidate] = None
    reverse: Optional[PrimerCandidate] = None
    product_size: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class PrimerDesignSummary(BaseModel):
    """Summary statistics for designed primer sets."""

    # purpose: enable dashboards to present aggregated primer metrics
    primer_count: int
    average_tm: float
    min_tm: float
    max_tm: float


class PrimerDesignResponse(BaseModel):
    """Full primer design response structure."""

    # purpose: share primer results plus summary statistics
    primers: List[PrimerDesignRecord]
    summary: PrimerDesignSummary


class AssemblyStepMetrics(BaseModel):
    """Per-template assembly assessment."""

    # purpose: expose assembly scoring inputs to downstream governance
    template: str
    strategy: str
    expected_fragment_count: int
    junction_success: float = Field(ge=0.0, le=1.0)
    ligation_efficiency: float = Field(default=0.85, ge=0.0, le=1.0)
    kinetics_score: float = Field(default=0.0, ge=0.0, le=1.0)
    heuristics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    metadata_tags: List[str] = Field(default_factory=list)


class AssemblySimulationResult(BaseModel):
    """Structured assembly simulation payload."""

    # purpose: align assembly outputs with governance and planner pipelines
    strategy: str
    steps: List[AssemblyStepMetrics]
    average_success: float = Field(ge=0.0, le=1.0)
    min_success: float = Field(ge=0.0, le=1.0)
    max_success: float = Field(ge=0.0, le=1.0)
    payload_contract: Dict[str, Any] = Field(default_factory=dict)


class QCReport(BaseModel):
    """Individual QC checkpoint report."""

    # purpose: unify QC telemetry across planner and governance dashboards
    template: Optional[str]
    checkpoint: str
    status: str
    details: Dict[str, Any]


class QCReportResponse(BaseModel):
    """Collection of QC reports for a run."""

    # purpose: allow API responses to provide typed QC payloads
    reports: List[QCReport]

