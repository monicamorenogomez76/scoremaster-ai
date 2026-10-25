from __future__ import annotations

import math

from backend.analyzers.criticality import detect_critical_passages
from backend.analyzers.rubric_grade import rubric_grade
from backend.domain.difficulty_scale import SCALE, grade_from_index
from backend.domain.models import Score
from backend.analyzers.instrument_difficulty import (
    classify_instrument_family,
    compute_instrument_difficulty,
    family_label_es,
    grade_from_score,
    instrument_label_es,
)
from backend.rules.high_density import find_high_rhythm_density
from backend.rules.high_register import find_high_register
from backend.rules.large_intervals import find_large_intervals
from backend.rules.endurance import find_long_passages_without_rest
from backend.rules.weights import RULE_WEIGHTS

# difficulty-v2 (author's review, 2026-10-14): density in notes per second at the local tempo, typical
# instead of peak, longer endurance, cornets as trumpets, and the work graded by its winds and strings.
# difficulty-v3 (author's decision, 2026-10-25): the grades of the work, its families and its parts follow the
# publishers' grading guides (backend/analyzers/rubric_grade.py); the technical index and its dimensions stay
# for the critical passages and the explanations.
DIFFICULTY_VERSION = "difficulty-v3"
# Families whose grade is the work's grade. Percussion, the rhythm section, keyboards and parts without an
# identified instrument keep their own grade, shown apart: their estimate is provisional and they used to
# raise whole works (a snare drum in quavers made Persis a 6 against its publisher's Grade 4).
WORK_FAMILIES = ("woodwinds", "brass", "strings")



def _difficulty_level(score_value: int) -> str:
    if score_value == 0:
        return "low"
    if score_value <= 4:
        return "moderate"
    if score_value <= 8:
        return "high"
    return "very_high"


def _instrument_family(instrument: str) -> str:
    return classify_instrument_family(instrument)


def _measure_numbers(measure_range: str) -> tuple[int, int]:
    if "-" in measure_range:
        start_text, end_text = measure_range.split("-", 1)
        return int(start_text), int(end_text)
    value = int(measure_range)
    return value, value


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


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


def compute_difficulty_score(score: Score, critical_detector: str = "phrases", scale: str = "current") -> dict:
    """critical_detector: "phrases" (step 14) or "legacy"; scale: "current" (step 13: grades 1-6,
    index 0-10) or "legacy" (1-5, 0-5). Both legacy options are kept only for the baseline-v1 capture."""
    """Aggregate rule findings into a deterministic overall difficulty score."""
    findings = []
    findings.extend(find_high_rhythm_density(score))
    findings.extend(find_large_intervals(score))
    findings.extend(find_high_register(score))
    findings.extend(find_long_passages_without_rest(score))

    by_instrument: dict[str, dict] = {}
    by_family: dict[str, dict] = {}
    critical_passages: list[dict] = []
    tempo_bpm = max(
        (
            mark.beats_per_minute * mark.beat_unit_quarters
            for mark in score.tempo_marks
        ),
        default=None,
    )
    instrument_analyses: dict[str, dict] = {}
    for part in score.parts:
        analysis = compute_instrument_difficulty(part, tempo_bpm, scale, score.tempo_marks)
        current = instrument_analyses.get(part.name)
        if current is None or (
            analysis["grade"], analysis["difficulty_score"]
        ) > (current["grade"], current["difficulty_score"]):
            instrument_analyses[part.name] = analysis

    for instrument, analysis in instrument_analyses.items():
        by_instrument[instrument] = {
            "score": 0,
            "findings": [],
            **analysis,
        }
        family_entry = by_family.setdefault(
            analysis["family"],
            {"score": 0, "instruments": set(), "findings": [], "difficulty_scores": []},
        )
        family_entry["instruments"].add(instrument)
        family_entry["difficulty_scores"].append(analysis["difficulty_score"])

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
            {"score": 0, "instruments": set(), "findings": [], "difficulty_scores": []},
        )
        family_entry["score"] += RULE_WEIGHTS.get(finding.code, 1)
        family_entry["instruments"].add(finding.instrument)
        family_entry["findings"].append(finding.code)

    if critical_detector == "legacy":
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
                        "instrument_label_es": instrument_label_es(instrument),
                        "family_label_es": family_label_es(_instrument_family(instrument)),
                        "measure_range": str(start) if start == end else f"{start}-{end}",
                        "score": passage_score,
                        "findings": sorted({finding.code for finding in passage_findings}),
                    }
                )

        critical_passages.sort(key=lambda passage: (-passage["score"], _measure_numbers(passage["measure_range"])[0]))
    else:
        # Step 14: evidence-based detector; passages cover whole melodic phrases.
        critical_passages = [{
            **passage,
            "family": by_instrument.get(passage["instrument"], {}).get("family", _instrument_family(passage["instrument"])),
            "instrument_label_es": instrument_label_es(passage["instrument"]),
            "family_label_es": family_label_es(by_instrument.get(passage["instrument"], {}).get("family", "other")),
        } for passage in detect_critical_passages(score, findings)]

    overall_score = sum(
        RULE_WEIGHTS.get(finding.code, 1) for finding in findings
    )
    grade = grade_from_score if scale == "legacy" else grade_from_index
    family_grades = {
        family: grade(_percentile(details["difficulty_scores"], 0.8))
        for family, details in by_family.items()
    }
    rubric = None
    if scale == "legacy":
        counted = family_grades
        overall_grade = max(counted.values(), default=1)
    else:
        counted = {family: value for family, value in family_grades.items() if family in WORK_FAMILIES} or family_grades
        rubric = rubric_grade(score)
        if rubric["by_instrument"]:
            family_grades = {**family_grades, **rubric["by_family"]}
            for instrument, details in rubric["by_instrument"].items():
                if instrument in by_instrument:
                    by_instrument[instrument]["grade"] = details["grade"]
            overall_grade = rubric["grade"]
        else:
            # Percussion alone: the guides grade percussion by its instruments only, so its difficulty-v2 grade stays.
            overall_grade = max(counted.values(), default=1)

    result = {
        "overall_score": overall_score,
        "level": _difficulty_level(overall_score),
        "grade": overall_grade,
        "grade_method": "family_percentile_80" if scale == "legacy" else
                        "publisher_rubric" if rubric["by_instrument"] else "winds_strings_percentile_80",
        "by_instrument": {
            instrument: {
                **details,
                "instrument_label_es": instrument_label_es(instrument),
                "family_label_es": family_label_es(details["family"]),
                "findings": sorted(set(details["findings"])),
            }
            for instrument, details in sorted(by_instrument.items())
        },
        "by_family": {
            family: {
                "label_es": family_label_es(family),
                "score": details["score"],
                "grade": family_grades[family],
                **({} if scale == "legacy" else {"counts_for_work": family in counted}),
                "instruments": sorted(details["instruments"]),
                "findings": sorted(set(details["findings"])),
            }
            for family, details in sorted(by_family.items())
        },
        "critical_passages": critical_passages,
    }
    return result if scale == "legacy" else {**result, "scale": SCALE, "algorithm_version": DIFFICULTY_VERSION,
                                             "rubric": rubric}
