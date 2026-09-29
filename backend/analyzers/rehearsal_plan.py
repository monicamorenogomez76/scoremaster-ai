from __future__ import annotations

from backend.domain.models import Score
from backend.rules.high_density import find_high_rhythm_density


def build_rehearsal_plan(score: Score, total_minutes: int) -> dict:
    """Build a simple rehearsal plan by prioritizing the most critical passages."""
    critical_segments = []
    critical_sections = {
        (finding.instrument, finding.measure_range)
        for finding in find_high_rhythm_density(score)
    }

    for part in score.parts:
        for measure in part.measures:
            measure_key = (part.name, str(measure.number))
            if measure_key in critical_sections:
                critical_segments.append(
                    {
                        "instrument": part.name,
                        "measure_range": str(measure.number),
                        "priority": "high",
                        "minutes": max(10, min(total_minutes // 2, 20)),
                        "reason": "High rhythmic density in the selected passage.",
                    }
                )

    if not critical_segments:
        critical_segments = [{
            "instrument": score.parts[0].name if score.parts else "N/A",
            "measure_range": "1",
            "priority": "high",
            "minutes": min(15, total_minutes),
            "reason": "Default rehearsal block.",
        }]

    return {
        "total_minutes": total_minutes,
        "segments": critical_segments,
    }
