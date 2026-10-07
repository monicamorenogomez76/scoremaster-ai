"""Passages proposed for the musicians' evaluation (steps 16-18, author's decisions, 2026-10-07).

A reproducible, stratified sample of the director's works: about 40 % critical passages (to measure
recall) and 60 % non-critical windows spread over grades (to measure false positives). Every passage
is one part and 4-12 measures long, and keeps the ScoreLint prediction for that very fragment, which
the musicians never see. The order is shuffled deterministically so critical passages are not grouped.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import zip_longest

from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.domain.difficulty_scale import SCALE
from backend.domain.models import Score, ScorePart

CRITICAL_SHARE = 0.4
WINDOW = 8
MIN_MEASURES, MAX_MEASURES = 4, 12
SAMPLE_VERSION = "evaluation-sample-v1"


@dataclass(frozen=True)
class WorkSample:
    work_id: str
    title: str
    score: Score
    # The stored analysis of the work (its critical passages).
    difficulty: dict


def _bounds(measures: str) -> tuple[int, int]:
    first, _, last = str(measures).partition("-")
    return int(first), int(last or first)


def _key(*parts) -> str:
    return sha256("|".join(map(str, parts)).encode()).hexdigest()


def _slice(part: ScorePart, first: int, last: int) -> ScorePart:
    return ScorePart(part.name, tuple(m for m in part.measures if first <= m.number <= last), part.metadata)


def _plays(part: ScorePart, first: int, last: int) -> bool:
    """At least half of the window's measures have notes."""
    bars = [m for m in part.measures if first <= m.number <= last]
    return bool(bars) and sum(any(not note.is_rest for note in m.notes) for m in bars) * 2 >= len(bars)


def _tempo(score: Score):
    return max((mark.beats_per_minute * mark.beat_unit_quarters for mark in score.tempo_marks), default=None)


def _passage(sample: WorkSample, part: ScorePart, first: int, last: int, critical: bool, findings) -> dict:
    prediction = compute_instrument_difficulty(_slice(part, first, last), _tempo(sample.score))
    measures = str(first) if first == last else f"{first}-{last}"
    return {
        "work_id": sample.work_id, "work_title": sample.title, "parts": [part.name], "measure_range": measures,
        "label": f"{part.name} · cc. {measures.replace('-', '–')}",
        "snapshot": {"grade": prediction["grade"], "technical_index": prediction["difficulty_score"],
                     "family": prediction["family"], "critical": critical, "findings": sorted(findings),
                     "versions": {"scale": SCALE["version"], "critical_detector": "phrases", "sample": SAMPLE_VERSION}},
        "_key": _key(sample.work_id, part.name, first),
    }


def _critical(sample: WorkSample) -> list[dict]:
    parts = {part.name: part for part in sample.score.parts}
    found = []
    for item in sample.difficulty.get("critical_passages", []):
        part = parts.get(item.get("instrument"))
        if part is None or not part.measures:
            continue
        lowest, highest = part.measures[0].number, part.measures[-1].number
        first, last = _bounds(item.get("core_range") or item["measure_range"])
        last = min(max(last, first + MIN_MEASURES - 1), first + MAX_MEASURES - 1, highest)
        first = max(lowest, min(first, last - MIN_MEASURES + 1))
        found.append(_passage(sample, part, first, last, True, item.get("findings", [])))
    return found


def _non_critical(sample: WorkSample) -> list[dict]:
    flagged = {}
    for item in sample.difficulty.get("critical_passages", []):
        flagged.setdefault(item.get("instrument"), []).append(_bounds(item["measure_range"]))
    found = []
    for part in sample.score.parts:
        if not part.measures:
            continue
        lowest, highest = part.measures[0].number, part.measures[-1].number
        for first in range(lowest, highest - MIN_MEASURES + 2, WINDOW):
            last = min(first + WINDOW - 1, highest)
            if any(first <= end and start <= last for start, end in flagged.get(part.name, [])):
                continue
            if _plays(part, first, last):
                found.append(_passage(sample, part, first, last, False, []))
    return found


def _interleave(groups: list[list[dict]]) -> list[dict]:
    """One from each group in turn, keeping each group's order."""
    return [item for row in zip_longest(*groups) for item in row if item is not None]


def _shuffled(group: list[dict]) -> list[dict]:
    """A stable pseudo-random order."""
    return sorted(group, key=lambda item: item["_key"])


def propose_passages(works: list[WorkSample], size: int) -> list[dict]:
    critical = _interleave([_shuffled(_critical(sample)) for sample in works])
    calm_by_work = [_non_critical(sample) for sample in works]
    grades = sorted({item["snapshot"]["grade"] for group in calm_by_work for item in group})
    # Non-critical windows spread over the grades, and over the works within each grade.
    calm = _interleave([_interleave([_shuffled([item for item in group if item["snapshot"]["grade"] == grade])
                                     for group in calm_by_work]) for grade in grades])
    wanted_critical = min(len(critical), round(size * CRITICAL_SHARE))
    chosen = critical[:wanted_critical] + calm[:size - wanted_critical]
    chosen += critical[wanted_critical:wanted_critical + size - len(chosen)]
    return [{key: value for key, value in item.items() if key != "_key"}
            for item in sorted(chosen, key=lambda item: _key("order", item["_key"]))]
