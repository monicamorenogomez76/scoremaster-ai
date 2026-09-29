from __future__ import annotations

from backend.domain.models import Score


def compute_band_fit(score: Score, band_profile: dict[str, int]) -> dict:
    """Compare required instrument capacity against the real band profile."""
    required = {}
    for part in score.parts:
        required[part.name] = required.get(part.name, 0) + 1

    issues = []
    total_required = 0
    total_available = 0

    for instrument, required_count in sorted(required.items()):
        available = int(band_profile.get(instrument, 0))
        total_required += required_count
        total_available += min(required_count, available)

        if available < required_count:
            severity = "critical" if available == 0 else "warning"
            issues.append(
                {
                    "instrument": instrument,
                    "severity": severity,
                    "message": (
                        f"{instrument} is under-capacity for the current band profile."
                        if available > 0
                        else f"{instrument} is missing from the current band profile."
                    ),
                    "required": required_count,
                    "available": available,
                }
            )

    compatibility_percent = 100 if total_required == 0 else int((total_available / total_required) * 100)

    if not issues:
        status = "ok"
    elif compatibility_percent < 50:
        status = "critical"
    else:
        status = "warning"

    return {
        "compatibility_percent": compatibility_percent,
        "status": status,
        "issues": issues,
    }
