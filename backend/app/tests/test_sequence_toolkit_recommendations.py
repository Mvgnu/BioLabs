from app.services import sequence_toolkit


def _sequence(name: str, repeat: str, copies: int = 60) -> dict[str, str]:
    return {"name": name, "sequence": repeat * copies}


def test_build_strategy_recommendations_returns_scorecard() -> None:
    templates = [_sequence("bundle", "ATGCGT", 75)]
    bundle = sequence_toolkit.build_strategy_recommendations(
        templates,
        preset_id="multiplex",
    )
    scorecard = bundle["scorecard"]
    assert scorecard["preset_id"] == "multiplex"
    assert scorecard["best_strategy"]
    assert bundle["strategy_scores"]
    assert bundle["assembly"]["strategy"]


def test_build_strategy_recommendations_works_without_preset() -> None:
    templates = [_sequence("presetless", "ATGCGA", 70)]
    bundle = sequence_toolkit.build_strategy_recommendations(templates)
    assert bundle["scorecard"]["preset_id"]
    assert bundle["primer"]["summary"]["primer_count"] >= 0
    assert "recommended_buffers" in bundle["scorecard"]
