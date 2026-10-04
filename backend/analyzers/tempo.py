from __future__ import annotations

from backend.domain.models import Score, TempoMark


def _quarter_bpm(mark: TempoMark) -> float:
    return round(mark.beats_per_minute * mark.beat_unit_quarters, 2)


def compute_tempo_metrics(score: Score) -> dict:
    """Summarize numeric tempo changes using quarter notes per minute."""
    unique_marks = set(score.tempo_marks)
    marks = sorted(
        unique_marks,
        key=lambda mark: (mark.measure_number, mark.offset_quarters, mark.beats_per_minute),
    )
    if not marks:
        return {
            "tempo_mark_count": 0,
            "tempo_change_count": 0,
            "min_quarter_bpm": None,
            "max_quarter_bpm": None,
            "range_quarter_bpm": None,
            "changes": [],
        }

    quarter_bpms = [_quarter_bpm(mark) for mark in marks]
    changes = []
    for previous, current, previous_bpm, current_bpm in zip(
        marks, marks[1:], quarter_bpms, quarter_bpms[1:]
    ):
        if current_bpm == previous_bpm:
            continue
        changes.append(
            {
                "measure_number": current.measure_number,
                "offset_quarters": current.offset_quarters,
                "from_quarter_bpm": previous_bpm,
                "to_quarter_bpm": current_bpm,
            }
        )

    minimum = min(quarter_bpms)
    maximum = max(quarter_bpms)
    return {
        "tempo_mark_count": len(marks),
        "tempo_change_count": len(changes),
        "min_quarter_bpm": minimum,
        "max_quarter_bpm": maximum,
        "range_quarter_bpm": round(maximum - minimum, 2),
        "changes": changes,
    }

ASSUMED_QUARTER_BPM = 100.0


def estimate_duration(score: Score) -> dict:
    """Playing time from the measures of the first part and the tempo in force in each one
    (quarter = 100 when the score has no tempo mark). Repeats are not expanded."""
    if not score.parts:
        return {"seconds": 0, "assumed_tempo": True}
    marks = sorted(score.tempo_marks, key=lambda mark: (mark.measure_number, mark.offset_quarters))
    seconds, current, index = 0.0, None, 0
    for measure in score.parts[0].measures:
        while index < len(marks) and marks[index].measure_number <= measure.number:
            current = _quarter_bpm(marks[index])
            index += 1
        quarters = measure.duration_quarters or sum(note.duration_quarters for note in measure.notes)
        seconds += quarters * 60.0 / (current or ASSUMED_QUARTER_BPM)
    return {"seconds": round(seconds), "assumed_tempo": not marks}
