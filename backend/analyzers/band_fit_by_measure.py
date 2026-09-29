from __future__ import annotations

from backend.domain.models import Score


def compute_band_fit_by_measure(score: Score, band_profile: dict[str, int]) -> dict:
    """Evaluate instrument capacity per measure segment, not only globally."""
    segments = []

    for part in score.parts:
        for measure in part.measures:
            available = int(band_profile.get(part.name, 0))
            required = 1
            if available < required:
                segments.append(
                    {
                        "instrument": part.name,
                        "measure_range": str(measure.number),
                        "required": required,
                        "available": available,
                        "status": "critical",
                    }
                )

    status = "critical" if segments else "ok"
    return {
        "status": status,
        "segments": segments,
    }
