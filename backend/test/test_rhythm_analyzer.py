from pathlib import Path

from backend.analyzers.rhythm import compute_rhythm_metrics
from backend.parsers.musicxml_parser import parse_musicxml


def test_compute_rhythm_metrics_counts_notes_rests_and_measures():
    score_path = Path(__file__).parents[2] / "test-scores" / "measure_with_rest.musicxml"

    score = parse_musicxml(score_path)
    metrics = compute_rhythm_metrics(score)

    assert metrics["total_measures"] == 2
    assert metrics["total_notes"] == 2
    assert metrics["total_rests"] == 1
    assert metrics["notes_per_measure"] == [1, 1]
    assert metrics["quarter_lengths_per_measure"] == [2.0, 2.0]
