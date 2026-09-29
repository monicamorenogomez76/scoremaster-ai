from __future__ import annotations

from music21 import pitch

from backend.domain.models import Score


def compute_range_metrics(score: Score) -> dict:
    """Compute range metrics for the whole score."""
    note_pitches = []

    for part in score.parts:
        for measure in part.measures:
            for note_event in measure.notes:
                if not note_event.is_rest and note_event.pitch is not None:
                    note_pitches.append(pitch.Pitch(note_event.pitch))

    if not note_pitches:
        return {
            "min_pitch": None,
            "max_pitch": None,
            "pitch_span_semitones": 0,
            "high_register_notes": 0,
        }

    min_pitch = min(note_pitches)
    max_pitch = max(note_pitches)
    pitch_span_semitones = int(max_pitch.midi - min_pitch.midi)
    high_register_notes = sum(
        1 for current in note_pitches if current.midi >= pitch.Pitch("C5").midi
    )

    return {
        "min_pitch": min_pitch.nameWithOctave,
        "max_pitch": max_pitch.nameWithOctave,
        "pitch_span_semitones": pitch_span_semitones,
        "high_register_notes": high_register_notes,
    }
