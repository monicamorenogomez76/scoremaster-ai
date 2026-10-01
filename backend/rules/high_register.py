from __future__ import annotations

from music21 import pitch

from backend.domain.models import Finding, Score


def find_high_register(score: Score) -> list[Finding]:
    """Detect measures where a large share of notes sits in a high register."""
    findings: list[Finding] = []
    high_register_threshold = 2

    for part in score.parts:
        for measure in part.measures:
            high_notes = [
                note
                for note in measure.notes
                if not note.is_rest and note.pitch is not None and pitch.Pitch(note.pitch).midi >= pitch.Pitch("C5").midi
            ]

            if len(high_notes) >= high_register_threshold:
                findings.append(
                    Finding(
                        code="SL002",
                        severity="warning",
                        instrument=part.name,
                        measure_range=str(measure.number),
                        description="High register demand",
                        evidence={
                            "measure": measure.number,
                            "high_notes_count": len(high_notes),
                            "threshold": high_register_threshold,
                        },
                    )
                )

    return findings
