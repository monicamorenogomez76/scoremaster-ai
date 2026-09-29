from __future__ import annotations

from music21 import pitch

from backend.domain.models import Finding, Score


def find_large_intervals(score: Score) -> list[Finding]:
    """Detect large melodic leaps that are especially demanding at a high tempo."""
    findings: list[Finding] = []
    leap_threshold = 7

    for part in score.parts:
        for measure in part.measures:
            pitched_notes = [
                note for note in measure.notes if not note.is_rest and note.pitch is not None
            ]
            if len(pitched_notes) < 2:
                continue

            for index in range(1, len(pitched_notes)):
                previous = pitch.Pitch(pitched_notes[index - 1].pitch)
                current = pitch.Pitch(pitched_notes[index].pitch)
                interval = abs(current.midi - previous.midi)

                if interval >= leap_threshold:
                    findings.append(
                        Finding(
                            code="SL004",
                            severity="warning",
                            instrument=part.name,
                            measure_range=str(measure.number),
                            description="Large intervals at high tempo",
                            evidence={
                                "measure": measure.number,
                                "interval_semitones": interval,
                                "from_pitch": previous.nameWithOctave,
                                "to_pitch": current.nameWithOctave,
                                "threshold": leap_threshold,
                            },
                        )
                    )
                    break

    return findings
