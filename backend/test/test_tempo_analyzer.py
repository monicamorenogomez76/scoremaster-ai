from backend.analyzers.tempo import compute_tempo_metrics
from backend.domain.models import Score, TempoMark


def test_compute_tempo_metrics_normalizes_pulse_units_and_counts_changes():
    score = Score(
        title="Tempo study",
        parts=(),
        tempo_marks=(
            TempoMark(1, 0.0, 60.0, 1.0),
            TempoMark(2, 0.0, 120.0, 0.5),
            TempoMark(3, 0.0, 90.0, 1.0),
        ),
    )

    metrics = compute_tempo_metrics(score)

    assert metrics["tempo_mark_count"] == 3
    assert metrics["tempo_change_count"] == 1
    assert metrics["min_quarter_bpm"] == 60.0
    assert metrics["max_quarter_bpm"] == 90.0
    assert metrics["range_quarter_bpm"] == 30.0
    assert metrics["changes"] == [
        {
            "measure_number": 3,
            "offset_quarters": 0.0,
            "from_quarter_bpm": 60.0,
            "to_quarter_bpm": 90.0,
        }
    ]


def test_compute_tempo_metrics_without_marks_returns_empty_summary():
    score = Score(title="No tempo", parts=())

    assert compute_tempo_metrics(score) == {
        "tempo_mark_count": 0,
        "tempo_change_count": 0,
        "min_quarter_bpm": None,
        "max_quarter_bpm": None,
        "range_quarter_bpm": None,
        "changes": [],
    }