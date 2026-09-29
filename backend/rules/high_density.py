from __future__ import annotations

from backend.domain.models import Finding, Score


def find_high_rhythm_density(score: Score) -> list[Finding]:
    """Detect measures with high non-rest note density.

    This is the first deterministic rule in the ScoreLint pipeline. It does not
    rely on an LLM; it simply measures the musical load in each measure.
    """
    findings: list[Finding] = []
    density_threshold = 3.0

    for part in score.parts:
        for measure in part.measures:
            non_rest = [note for note in measure.notes if not note.is_rest]
            quarter_total = sum(note.duration_quarters for note in non_rest)

            if quarter_total > density_threshold:
                findings.append(
                    Finding(
                        code="SL003",
                        severity="warning",
                        instrument=part.name,
                        measure_range=str(measure.number),
                        description="High rhythmic density",
                        evidence={
                            "measure": measure.number,
                            "quarter_total": round(quarter_total, 2),
                            "threshold": density_threshold,
                        },
                    )
                )

    return findings
