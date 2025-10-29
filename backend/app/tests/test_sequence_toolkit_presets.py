from __future__ import annotations

from app.services import sequence_toolkit


def _sequence(name: str, repeat: str, copies: int = 60) -> dict[str, str]:
    return {"name": name, "sequence": repeat * copies}


def test_design_primers_reports_multiplex_metadata() -> None:
    templates = [_sequence("amplicon", "ATGCGT", 80)]
    result = sequence_toolkit.design_primers(
        templates,
        preset_id="multiplex",
    )
    assert result["profile"]["preset_id"] == "multiplex"
    assert result["multiplex"]["risk_level"] in {"ok", "review", "blocked"}
    assert "cross_dimer_flags" in result["multiplex"]


def test_restriction_digest_returns_strategy_scores() -> None:
    templates = [_sequence("vector", "ATGCGA", 70)]
    digest = sequence_toolkit.analyze_restriction_digest(
        templates,
        preset_id="multiplex",
    )
    strategies = digest["strategy_scores"]
    assert any(entry["strategy"] == "double_digest" for entry in strategies)
    assert any(entry["strategy"] == "golden_gate" for entry in strategies)
    assert digest["profile"]["preset_id"] == "multiplex"


def test_simulate_assembly_propagates_profile_metadata() -> None:
    templates = [_sequence("construct", "ATGGCC", 75)]
    primers = sequence_toolkit.design_primers(templates, preset_id="high_gc")
    digest = sequence_toolkit.analyze_restriction_digest(templates, preset_id="high_gc")
    assembly = sequence_toolkit.simulate_assembly(
        primers,
        digest,
        preset_id="high_gc",
    )
    assert assembly["profile"]["preset_id"] == "high_gc"
    assert assembly["metadata_tags"]
