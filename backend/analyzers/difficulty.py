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

INSTRUMENT_FAMILIES = {
    "woodwinds": ("flute", "oboe", "clarinet", "bassoon", "piccolo", "sax", "english horn"),
    "brass": ("trumpet", "horn", "trombone", "tuba", "flugelhorn", "cornet", "baritone"),
    "strings": ("violin", "viola", "cello", "bass", "double bass"),
    "percussion": ("snare", "drum", "timpani", "percussion", "triangle", "marimba", "xylophone"),
    "keyboard": ("piano", "harp", "keyboard"),
}


def _difficulty_level(score_value: int) -> str:
    if score_value == 0:
        return "low"
    if score_value <= 4:
        return "moderate"
    if score_value <= 8:
        return "high"
    return "very_high"


def _instrument_family(instrument: str) -> str:
    lowered = instrument.lower()
    for family, tokens in INSTRUMENT_FAMILIES.items():
        if any(token in lowered for token in tokens):
            return family
    return "other"


def _measure_numbers(measure_range: str) -> tuple[int, int]:
    if "-" in measure_range:
        start_text, end_text = measure_range.split("-", 1)
        return int(start_text), int(end_text)
    value = int(measure_range)
    return value, value


def _collapse_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []

    ordered = sorted(ranges)
    collapsed = [ordered[0]]
    for start, end in ordered[1:]:
        previous_start, previous_end = collapsed[-1]
        if start <= previous_end + 1:
            collapsed[-1] = (previous_start, max(previous_end, end))
        else:
            collapsed.append((start, end))
    return collapsed


def compute_difficulty_score(score: Score) -> dict:
    """Aggregate rule findings into a deterministic overall difficulty score."""
    findings = []
    findings.extend(find_high_rhythm_density(score))
    findings.extend(find_large_intervals(score))
    findings.extend(find_high_register(score))

    by_instrument: dict[str, dict] = {}
    by_family: dict[str, dict] = {}
    critical_passages: list[dict] = []

    for finding in findings:
        instrument_entry = by_instrument.setdefault(
            finding.instrument,
            {"score": 0, "findings": []},
        )
        instrument_entry["score"] += RULE_WEIGHTS.get(finding.code, 1)
        instrument_entry["findings"].append(finding.code)

        family = _instrument_family(finding.instrument)
        family_entry = by_family.setdefault(
            family,
            {"score": 0, "instruments": set(), "findings": []},
        )
        family_entry["score"] += RULE_WEIGHTS.get(finding.code, 1)
        family_entry["instruments"].add(finding.instrument)
        family_entry["findings"].append(finding.code)

    for instrument, details in by_instrument.items():
        instrument_findings = [finding for finding in findings if finding.instrument == instrument]
        ranges = [_measure_numbers(finding.measure_range) for finding in instrument_findings]
        collapsed_ranges = _collapse_ranges(ranges)
        for start, end in collapsed_ranges:
            passage_findings = [
                finding for finding in instrument_findings
                if start <= _measure_numbers(finding.measure_range)[0] <= end
                or start <= _measure_numbers(finding.measure_range)[1] <= end
            ]
            passage_score = sum(RULE_WEIGHTS.get(finding.code, 1) for finding in passage_findings)
            critical_passages.append(
                {
                    "instrument": instrument,
                    "family": _instrument_family(instrument),
                    "measure_range": str(start) if start == end else f"{start}-{end}",
                    "score": passage_score,
                    "findings": sorted({finding.code for finding in passage_findings}),
                }
            )

    critical_passages.sort(key=lambda passage: (-passage["score"], _measure_numbers(passage["measure_range"])[0]))

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
        "by_family": {
            family: {
                "score": details["score"],
                "instruments": sorted(details["instruments"]),
                "findings": sorted(set(details["findings"])),
            }
            for family, details in sorted(by_family.items())
        },
        "critical_passages": critical_passages,
    }
