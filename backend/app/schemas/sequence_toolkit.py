"""Configuration schemas for sequence toolkit operations."""

# purpose: capture scientific configuration profiles for shared sequence computations
# status: experimental
# related_docs: docs/dna_assets.md

from __future__ import annotations

from typing import Tuple, List

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


class RestrictionDigestConfig(BaseModel):
    """Restriction digest heuristic configuration."""

    # purpose: specify enzyme catalog defaults and compatibility heuristics
    enzymes: List[str] = Field(
        default_factory=lambda: ["EcoRI", "BamHI", "BsaI", "BsmBI"],
    )
    require_all: bool = True


class AssemblySimulationConfig(BaseModel):
    """Assembly simulation parameters."""

    # purpose: configure assembly scoring heuristics for planner and DNA asset simulations
    strategy: str = "gibson"
    base_success: float = Field(default=0.85, ge=0.0, le=1.0)
    tm_penalty_factor: float = Field(default=0.1, ge=0.0)
    minimal_site_count: int = Field(default=2, ge=0)
    low_site_penalty: float = Field(default=0.4, ge=0.0, le=1.0)


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
            primer=self.primer.copy(),
            restriction=self.restriction.copy(),
            assembly=self.assembly.copy(update={"strategy": strategy}),
            qc=self.qc.copy(),
        )

