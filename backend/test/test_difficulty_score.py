from pathlib import Path

from backend.analyzers.difficulty import compute_difficulty_score
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_difficulty_score_aggregates_rule_findings():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"

    score = parse_musicxml(score_path)
    result = compute_difficulty_score(score)

    assert result["overall_score"] >= 2
    assert result["level"] in {"moderate", "high", "very_high"}
    assert "Clarinet" in result["by_instrument"]
    assert result["by_instrument"]["Clarinet"]["score"] >= 2


def test_compute_difficulty_score_groups_critical_passages_by_instrument_and_family():
    score = Score(
        title="Critical passage grouping",
        parts=(
            ScorePart(
                name="Clarinet",
                measures=(
                    ScoreMeasure(
                        number=10,
                        notes=(
                            ScoreNote("C4", 0.5, False),
                            ScoreNote("D4", 0.5, False),
                            ScoreNote("E4", 0.5, False),
                            ScoreNote("F4", 0.5, False),
                            ScoreNote("G4", 0.5, False),
                            ScoreNote("A4", 0.5, False),
                            ScoreNote("B4", 0.5, False),
                            ScoreNote("C5", 0.5, False),
                        ),
                    ),
                    ScoreMeasure(
                        number=11,
                        notes=(
                            ScoreNote("D5", 0.5, False),
                            ScoreNote("E5", 0.5, False),
                            ScoreNote("F5", 0.5, False),
                            ScoreNote("G5", 0.5, False),
                            ScoreNote("A5", 0.5, False),
                            ScoreNote("B5", 0.5, False),
                            ScoreNote("C6", 0.5, False),
                            ScoreNote("D6", 0.5, False),
                        ),
                    ),
                ),
            ),
            ScorePart(
                name="Trumpet",
                measures=(
                    ScoreMeasure(
                        number=20,
                        notes=(
                            ScoreNote("C4", 0.5, False),
                            ScoreNote("D4", 0.5, False),
                            ScoreNote("E4", 0.5, False),
                            ScoreNote("F4", 0.5, False),
                            ScoreNote("G4", 0.5, False),
                            ScoreNote("A4", 0.5, False),
                            ScoreNote("B4", 0.5, False),
                            ScoreNote("C5", 0.5, False),
                        ),
                    ),
                ),
            ),
        ),
    )

    result = compute_difficulty_score(score)

    assert result["critical_passages"][0]["instrument"] == "Clarinet"
    assert result["critical_passages"][0]["family"] == "woodwinds"
    assert result["critical_passages"][0]["measure_range"] == "10-11"
    assert "woodwinds" in result["by_family"]
    assert result["by_family"]["woodwinds"]["score"] >= 2
