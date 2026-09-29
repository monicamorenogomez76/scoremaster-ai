from pathlib import Path

from backend.analyzers.difficulty import compute_difficulty_score
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_difficulty_score_aggregates_rule_findings():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"

    score = parse_musicxml(score_path)
    result = compute_difficulty_score(score)

    assert result["overall_score"] >= 2
    assert result["level"] in {"moderate", "high", "very_high"}
    assert "Clarinet" in result["by_instrument"]
    assert result["by_instrument"]["Clarinet"]["score"] >= 2
