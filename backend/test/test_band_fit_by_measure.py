from pathlib import Path

from backend.analyzers.band_fit_by_measure import compute_band_fit_by_measure
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_band_fit_by_measure_uses_measure_segments():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"
    score = parse_musicxml(score_path)

    result = compute_band_fit_by_measure(score, {"Clarinet": 0})

    assert result["status"] == "critical"
    assert result["segments"][0]["measure_range"] == "1"
    assert result["segments"][0]["instrument"] == "Clarinet"
    assert result["segments"][0]["available"] == 0
