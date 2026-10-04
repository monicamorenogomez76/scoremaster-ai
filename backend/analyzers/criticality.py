"""Critical passage detector (step 14).

A passage is critical only with enough evidence, never because it is in a Top N, so a piece can
have zero critical passages. Signals, per part and measure (initial values, configurable):
- local score: weights of the rules that flag the measure; the continuity rule (SL005) is evidence
  of persistence, not of local difficulty, so it does not add to the score;
- absolute: the local score reaches a threshold;
- relative + prominence: the measure is in the top percentile of the part and stands out from the
  median of the surrounding measures (uniform difficulty does not stand out);
- persistence: the core lasts a minimum number of beats;
- evidence: several distinct rules flag the core;
- speed: notes per second at the written tempo (fast runs are critical with a single warning).
The core is then widened to the whole melodic phrases it touches: a passage never cuts a phrase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from backend.analyzers.phrases import find_phrases
from backend.domain.models import Finding, Score, ScorePart, TempoMark
from backend.rules.weights import RULE_WEIGHTS

PERSISTENCE_RULES = {"SL005"}


@dataclass(frozen=True)
class CriticalityPolicy:
    absolute: float = 5.0
    percentile: float = 0.85
    prominence: float = 2.0
    context_measures: int = 4
    min_beats: float = 4.0
    min_rules: int = 2
    speed: float = 8.0  # notes per second: sixteenths at quarter = 120
    weights: dict = field(default_factory=lambda: dict(RULE_WEIGHTS))


def _bounds(measure_range: str) -> tuple[int, int]:
    first, _, last = str(measure_range).partition("-")
    return int(first), int(last or first)


def _range(first: int, last: int) -> str:
    return str(first) if first == last else "{}-{}".format(first, last)


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * (len(ordered) - 1) + 0.5))]


def _quarter_bpm(marks: tuple[TempoMark, ...], number: int) -> float | None:
    """Tempo in force at the start of a measure, in quarter notes per minute."""
    current = None
    for mark in sorted(marks, key=lambda mark: (mark.measure_number, mark.offset_quarters)):
        if mark.measure_number > number:
            break
        current = mark.beats_per_minute * mark.beat_unit_quarters
    return current


def _notes_per_second(measure, bpm: float | None) -> float:
    attacks = sum(1 for note in measure.notes if not note.is_rest)
    quarters = measure.duration_quarters or sum(note.duration_quarters for note in measure.notes)
    if not bpm or not quarters:
        return 0.0
    return attacks / (quarters * 60.0 / bpm)


def _part_passages(part: ScorePart, findings: list[Finding], policy: CriticalityPolicy,
                   tempo_marks: tuple[TempoMark, ...] = ()) -> list[dict]:
    numbers = [measure.number for measure in part.measures]
    beats = {measure.number: measure.duration_quarters or 4.0 for measure in part.measures}
    fast = {measure.number for measure in part.measures
            if _notes_per_second(measure, _quarter_bpm(tempo_marks, measure.number)) >= policy.speed}
    scores = {number: 0.0 for number in numbers}
    codes: dict[int, set[str]] = {number: set() for number in numbers}
    for item in findings:
        first, last = _bounds(item.measure_range)
        for number in range(first, last + 1):
            if number in scores:
                codes[number].add(item.code)
                if item.code not in PERSISTENCE_RULES:
                    scores[number] += policy.weights.get(item.code, 1)
    flagged = [value for value in scores.values() if value > 0]
    if not flagged:
        return []
    top = _percentile(flagged, policy.percentile)
    signals: dict[int, set[str]] = {}
    for number, value in scores.items():
        if value <= 0:
            continue
        if number in fast:
            signals[number] = {"speed"}
        context = [scores[other] for other in numbers
                   if other != number and abs(other - number) <= policy.context_measures]
        found = set()
        if value >= policy.absolute:
            found.add("absolute")
        if value >= top and value - (median(context) if context else 0.0) >= policy.prominence:
            found |= {"relative", "prominence"}
        if found:
            signals[number] = signals.get(number, set()) | found

    cores, current = [], []
    for number in sorted(signals):
        if current and number != current[-1] + 1:
            cores.append(current)
            current = []
        current.append(number)
    if current:
        cores.append(current)

    phrases = find_phrases(part)
    passages = []
    for core in cores:
        core_rules = set().union(*(codes[number] for number in core))
        # A fast run is evidence on its own; other cores need several kinds of warning.
        enough_evidence = len(core_rules) >= policy.min_rules or all(number in fast for number in core)
        if sum(beats[number] for number in core) < policy.min_beats or not enough_evidence:
            continue
        first, last = core[0], core[-1]
        touched = [phrase for phrase in phrases if phrase.first_measure <= last and phrase.last_measure >= first]
        start = min([first] + [phrase.first_measure for phrase in touched])
        end = max([last] + [phrase.last_measure for phrase in touched])
        passages.append({"first": start, "last": end, "core": [(first, last)],
                         "signals": set().union(*(signals[number] for number in core))})

    merged: list[dict] = []
    for passage in sorted(passages, key=lambda item: item["first"]):
        if merged and passage["first"] <= merged[-1]["last"] + 1:
            merged[-1]["last"] = max(merged[-1]["last"], passage["last"])
            merged[-1]["core"] += passage["core"]
            merged[-1]["signals"] |= passage["signals"]
        else:
            merged.append(passage)
    return [{
        "instrument": part.name,
        "measure_range": _range(passage["first"], passage["last"]),
        "core_range": _range(min(core[0] for core in passage["core"]), max(core[1] for core in passage["core"])),
        "score": round(sum(scores[n] for n in numbers if passage["first"] <= n <= passage["last"]), 2),
        "findings": sorted(set().union(*(codes[n] for n in numbers if passage["first"] <= n <= passage["last"])))
        ,
        "signals": sorted(passage["signals"]),
    } for passage in merged]


def detect_critical_passages(score: Score, findings: list[Finding], policy: CriticalityPolicy = CriticalityPolicy()) -> list[dict]:
    by_part: dict[str, list[Finding]] = {}
    for item in findings:
        by_part.setdefault(item.instrument, []).append(item)
    passages = []
    for part in score.parts:
        if part.name in by_part:
            passages.extend(_part_passages(part, by_part[part.name], policy, score.tempo_marks))
    return sorted(passages, key=lambda passage: (-passage["score"], _bounds(passage["measure_range"])[0], passage["instrument"]))
