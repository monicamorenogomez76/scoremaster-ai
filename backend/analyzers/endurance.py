from __future__ import annotations

from backend.domain.models import ScorePart


def uninterrupted_passages(part: ScorePart) -> list[dict]:
    """Find active bars without explicit rests in score order.

    This is a continuity proxy, not a physiological fatigue estimate. Empty
    bars and bars containing any rest interrupt the passage.
    """
    passages = []
    current = None
    for measure in part.measures:
        active = any(not event.is_rest for event in measure.notes)
        has_rest = any(event.is_rest for event in measure.notes)
        if active and not has_rest:
            if current is None:
                current = {
                    "measure_start": measure.number,
                    "measure_end": measure.number,
                    "measure_count": 0,
                }
            current["measure_end"] = measure.number
            current["measure_count"] += 1
        elif current is not None:
            passages.append(current)
            current = None
    if current is not None:
        passages.append(current)
    return passages


def longest_active_run(part: ScorePart) -> int:
    return max((item["measure_count"] for item in uninterrupted_passages(part)), default=0)
