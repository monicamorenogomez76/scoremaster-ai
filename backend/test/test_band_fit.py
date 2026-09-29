from pathlib import Path

from backend.analyzers.band_fit import compute_band_fit
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_band_fit_detects_missing_instrument_capacity():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"
    score = parse_musicxml(score_path)

    result = compute_band_fit(score, {"Clarinet": 0})

    assert result["compatibility_percent"] == 0
    assert result["status"] == "critical"
    assert any(issue["instrument"] == "Clarinet" for issue in result["issues"])


def test_compute_band_fit_tracks_partial_capacity_for_multiple_parts():
    score = Score(
        title="Two clarinet parts",
        parts=(
            ScorePart(
                "Clarinet",
                (
                    ScoreMeasure(
                        1,
                        (ScoreNote("C4", 1.0, False),),
                    ),
                ),
            ),
            ScorePart(
                "Clarinet",
                (
                    ScoreMeasure(
                        2,
                        (ScoreNote("D4", 1.0, False),),
                    ),
                ),
            ),
        ),
    )

    result = compute_band_fit(score, {"Clarinet": 1})

    assert result["compatibility_percent"] == 50
    assert result["status"] == "warning"
    assert result["issues"][0]["required"] == 2
    assert result["issues"][0]["available"] == 1
