from __future__ import annotations

from backend.domain.models import Score
from backend.rules.high_density import find_high_rhythm_density
from backend.rules.high_register import find_high_register
from backend.rules.large_intervals import find_large_intervals


RULE_WEIGHTS = {
    "SL003": 2,
    "SL004": 3,
    "SL005": 2,
}


def _difficulty_level(score_value: int) -> str:
    if score_value == 0:
        return "low"
    if score_value <= 4:
        return "moderate"
    if score_value <= 8:
        return "high"
    return "very_high"


def compute_difficulty_score(score: Score) -> dict:
    """Aggregate rule findings into a deterministic overall difficulty score."""
    findings = []
    findings.extend(find_high_rhythm_density(score))
    findings.extend(find_large_intervals(score))
    findings.extend(find_high_register(score))

    by_instrument: dict[str, dict] = {}
    for finding in findings:
        instrument_entry = by_instrument.setdefault(
            finding.instrument,
            {"score": 0, "findings": []},
        )
        instrument_entry["score"] += RULE_WEIGHTS.get(finding.code, 1)
        instrument_entry["findings"].append(finding.code)

    overall_score = sum(
        RULE_WEIGHTS.get(finding.code, 1) for finding in findings
    )

    return {
        "overall_score": overall_score,
        "level": _difficulty_level(overall_score),
        "by_instrument": {
            instrument: {
                "score": details["score"],
                "findings": sorted(set(details["findings"])),
            }
            for instrument, details in sorted(by_instrument.items())
        },
    }
