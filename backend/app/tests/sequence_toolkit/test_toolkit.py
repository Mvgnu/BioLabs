"""Regression coverage for sequence toolkit thermodynamics and catalogs."""

# purpose: verify enzyme catalog loading and thermodynamic outputs remain deterministic
# status: active

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
