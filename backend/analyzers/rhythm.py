from __future__ import annotations

from backend.domain.models import Score


def compute_rhythm_metrics(score: Score) -> dict:
    """Compute simple rhythm metrics from a parsed score.

    The result is intentionally compact and deterministic so it can be used as the
    foundation of ScoreLint before any generative AI layer is applied.
    """
    total_measures = 0
    total_notes = 0
    total_rests = 0
    notes_per_measure: list[int] = []
    quarter_lengths_per_measure: list[float] = []

    for part in score.parts:
        for measure in part.measures:
            total_measures += 1
            measure_notes = [note for note in measure.notes if not note.is_rest]
            measure_rests = [note for note in measure.notes if note.is_rest]
            notes_per_measure.append(len(measure_notes))
            quarter_lengths_per_measure.append(
                sum(note.duration_quarters for note in measure.notes)
            )
            total_notes += len(measure_notes)
            total_rests += len(measure_rests)

    return {
        "total_measures": total_measures,
        "total_notes": total_notes,
        "total_rests": total_rests,
        "notes_per_measure": notes_per_measure,
        "quarter_lengths_per_measure": quarter_lengths_per_measure,
    }
