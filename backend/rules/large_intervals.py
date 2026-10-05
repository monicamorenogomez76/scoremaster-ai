from __future__ import annotations

from music21 import pitch

from backend.domain.models import Finding, Score
from backend.domain.timing import melodic_lines


def find_large_intervals(score: Score) -> list[Finding]:
    """Detect large melodic leaps that are especially demanding at a high tempo."""
    findings: list[Finding] = []
    leap_threshold = 7

    for part in score.parts:
        for measure in part.measures:
            # Each voice is one player: leaps are only measured along a voice.
            leaps = (
                (pitch.Pitch(left), pitch.Pitch(right))
                for line in melodic_lines([measure]).values()
                for left, right in zip(line, line[1:])
                if abs(pitch.Pitch(right).midi - pitch.Pitch(left).midi) >= leap_threshold
            )
            leap = next(leaps, None)
            if leap is None:
                continue
            previous, current = leap
            findings.append(
                Finding(
                    code="SL004",
                    severity="warning",
                    instrument=part.name,
                    measure_range=str(measure.number),
                    description="Large intervals at high tempo",
                    evidence={
                        "measure": measure.number,
                        "interval_semitones": abs(current.midi - previous.midi),
                        "from_pitch": previous.nameWithOctave,
                        "to_pitch": current.nameWithOctave,
                        "threshold": leap_threshold,
                    },
                )
            )

    return findings
