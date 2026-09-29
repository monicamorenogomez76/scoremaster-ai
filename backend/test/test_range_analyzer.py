from pathlib import Path

from backend.analyzers.range import compute_range_metrics
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_range_metrics_detects_register_span_and_high_notes():
    score_path = Path(__file__).parents[2] / "test-scores" / "measure_with_rest.musicxml"

    score = parse_musicxml(score_path)
    metrics = compute_range_metrics(score)

    assert metrics["min_pitch"] == "C4"
    assert metrics["max_pitch"] == "E4"
    assert metrics["pitch_span_semitones"] == 4
    assert metrics["high_register_notes"] == 0
