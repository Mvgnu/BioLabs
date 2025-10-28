"""Regression coverage for sequence toolkit thermodynamics and catalogs."""

# purpose: verify enzyme catalog loading and thermodynamic outputs remain deterministic
# status: active

import pytest

from ...schemas.sequence_toolkit import (
    PrimerDesignConfig,
    RestrictionDigestConfig,
    SequenceToolkitProfile,
)
from ...services import sequence_toolkit


def test_get_enzyme_catalog_cached_reference():
    """Repeated catalog calls should reuse cached objects."""

    first = sequence_toolkit.get_enzyme_catalog()
    second = sequence_toolkit.get_enzyme_catalog()
    assert first is second
    assert any(entry.name == "EcoRI" for entry in first)


def test_get_reaction_buffers_cached_reference():
    """Reaction buffer catalog should be cached for cross-service reuse."""

    buffers_first = sequence_toolkit.get_reaction_buffers()
    buffers_second = sequence_toolkit.get_reaction_buffers()
    assert buffers_first is buffers_second
    assert any(buffer.name == "CutSmart" for buffer in buffers_first)


def test_design_primers_includes_thermodynamics():
    """Primer design responses expose thermodynamic metadata."""

    profile = SequenceToolkitProfile(
        primer=PrimerDesignConfig(product_size_range=(40, 80))
    )
    result = sequence_toolkit.design_primers(
        [
            {
                "name": "vector",
                "sequence": "ATGCGTCTAGATCGATCGATCGATCGATCGTCTAAGGTTCTAGAGGATCC",
            }
        ],
        config=profile,
    )
    record = result["primers"][0]
    assert record["status"] == "ok"
    forward = record["forward"]
    reverse = record["reverse"]
    assert forward["thermodynamics"]["tm"] > 40
    assert reverse["thermodynamics"]["tm"] > 40
    assert "thermodynamics" in forward
    assert "warnings" in record


def test_digest_reports_include_buffer_alerts():
    """Restriction digests surface buffer compatibility warnings."""

    digest_config = RestrictionDigestConfig(
        enzymes=["EcoRI"],
        reaction_buffer="Buffer X",
    )
    payload = sequence_toolkit.analyze_restriction_digest(
        [
            {
                "name": "vector",
                "sequence": "GAATTCTGCA",  # contains EcoRI site
            }
        ],
        config=digest_config,
    )
    digest = payload["digests"][0]
    assert digest["buffer_alerts"]
    assert any(
        "EcoRI" in note for note in digest["notes"]
    ), "Star activity notes should propagate to digest notes"
    assert payload["enzymes"][0]["name"] == "EcoRI"
    assert all(
        not alert.startswith("No catalog metadata") for alert in payload["alerts"]
    )


def test_simulate_assembly_includes_strategy_metrics():
    """Assembly simulation should surface ligation and kinetics heuristics."""

    primer_results = {
        "primers": [
            {
                "name": "vector",
                "status": "ok",
                "forward": {
                    "thermodynamics": {"tm": 60.0},
                    "length": 22,
                },
                "reverse": {
                    "thermodynamics": {"tm": 59.2},
                    "length": 21,
                },
                "product_size": 120,
                "warnings": [],
            }
        ]
    }
    digest_results = {
        "digests": [
            {
                "name": "vector",
                "compatible": True,
                "buffer_alerts": [],
                "notes": [],
                "buffer": {
                    "name": "CutSmart",
                    "ionic_strength_mM": 100,
                    "ph": 7.9,
                    "stabilizers": ["BSA"],
                    "compatible_strategies": [
                        "golden_gate",
                        "gibson",
                        "hifi",
                    ],
                    "notes": "",
                },
                "sites": {
                    "BsaI": {
                        "positions": [10, 80],
                        "metadata": {
                            "name": "BsaI",
                            "recognition_site": "GGTCTC",
                            "overhang": "AATT",
                        },
                    }
                },
            }
        ]
    }
    plan = sequence_toolkit.simulate_assembly(
        primer_results,
        digest_results,
        strategy="golden_gate",
    )
    step = plan["steps"][0]
    assert step["strategy"] == "golden_gate"
    assert pytest.approx(step["ligation_efficiency"], rel=1e-3) == 0.9
    assert 0.0 <= step["kinetics_score"] <= 1.0
    assert "kinetics_modifier" in step["heuristics"]
    assert plan["average_success"] == pytest.approx(
        step["junction_success"],
        rel=1e-6,
    )


def test_simulate_assembly_penalizes_buffer_incompatibility():
    """Buffers not matching strategy should introduce penalties."""

    primer_results = {
        "primers": [
            {
                "name": "insert",
                "status": "ok",
                "forward": {
                    "thermodynamics": {"tm": 62.0},
                    "length": 20,
                },
                "reverse": {
                    "thermodynamics": {"tm": 62.5},
                    "length": 20,
                },
                "product_size": 100,
                "warnings": [],
            }
        ]
    }
    digest_results = {
        "digests": [
            {
                "name": "insert",
                "compatible": True,
                "buffer_alerts": [],
                "notes": [],
                "buffer": {
                    "name": "Buffer 3.1",
                    "ionic_strength_mM": 150,
                    "ph": 7.0,
                    "stabilizers": ["DTT"],
                    "compatible_strategies": ["homologous_recombination"],
                    "notes": "",
                },
                "sites": {
                    "EcoRI": {
                        "positions": [5],
                        "metadata": {
                            "name": "EcoRI",
                            "recognition_site": "GAATTC",
                            "overhang": "AATT",
                        },
                    }
                },
            }
        ]
    }
    plan = sequence_toolkit.simulate_assembly(
        primer_results,
        digest_results,
        strategy="golden_gate",
    )
    step = plan["steps"][0]
    assert step["heuristics"]["buffer_penalty"] >= 0.1
    assert step["junction_success"] < 1.0
