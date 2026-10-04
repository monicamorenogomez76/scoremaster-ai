"""Common passages for ensemble rehearsal.

A common passage joins the critical passages of several parts that overlap in measures.
Shared material marks parts that play the same thing there: unison or octaves in sounding
pitch (written pitch plus the declared MusicXML transposition), or only the same rhythm.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from music21 import pitch as m21_pitch

from backend.domain.models import Score, ScorePart

# Longest rehearsal passage built by joining overlaps; keeps chains of overlaps from
# turning the whole piece into a single block.
MAX_PASSAGE_SPAN = 16


@dataclass(frozen=True)
class CommonPassage:
    first: int
    last: int
    parts: tuple[str, ...]
    findings: tuple[str, ...]
    score: int


@dataclass(frozen=True)
class CommonLine:
    """Parts that play the same thing in a passage: the same line or only the same rhythm."""
    parts: tuple[str, ...]
    kind: str  # "line" or "rhythm"


def _bounds(measure_range: str) -> tuple[int, int]:
    first, _, last = str(measure_range).partition("-")
    return int(first), int(last or first)


def group_common_passages(critical_passages: list[dict]) -> list[CommonPassage]:
    """Highest-priority passage first; it absorbs the passages inside it and those it overlaps
    while the joined span fits the limit."""
    pending = sorted(
        ({**passage, "bounds": _bounds(passage["measure_range"])} for passage in critical_passages),
        key=lambda passage: (-passage["score"], passage["bounds"][0], passage["instrument"]))
    passages = []
    while pending:
        seed = pending.pop(0)
        first, last = seed["bounds"]
        group = [seed]
        for candidate in list(pending):
            low, high = candidate["bounds"]
            inside = first <= low and high <= last
            grows_within_limit = max(last, high) - min(first, low) + 1 <= MAX_PASSAGE_SPAN
            # Passages inside the current one always join; growing it is capped.
            if low <= last and high >= first and (inside or grows_within_limit):
                first, last = min(first, low), max(last, high)
                group.append(candidate)
                pending.remove(candidate)
        passages.append(CommonPassage(
            first, last,
            tuple(sorted({passage["instrument"] for passage in group})),
            tuple(sorted({code for passage in group for code in passage.get("findings", [])})),
            sum(passage["score"] for passage in group)))
    return passages


# Author's decision (2026-10-04): parts play "the same" when they share the line (same rhythm
# and melodic intervals, in any key or octave) or only the rhythm.
LINE_INTERVAL_SHARE = 0.85   # within a measure, share of equal melodic intervals for "same line"
SHARED_MEASURE_SHARE = 0.75  # share of the measures where either part plays that must coincide


def _measures(part: ScorePart, first: int, last: int) -> dict[int, list[tuple[float, int | None, bool]]]:
    """(duration, sounding MIDI or None, is_rest) per measure, using the declared transposition."""
    transposition = part.metadata.transposition
    shift = transposition.chromatic + 12 * transposition.octave_change if transposition else 0
    return {measure.number: [(round(note.duration_quarters, 4),
                              None if note.is_rest or note.pitch is None else m21_pitch.Pitch(note.pitch).midi + shift,
                              note.is_rest) for note in measure.notes]
            for measure in part.measures if first <= measure.number <= last}


def _plays(events) -> bool:
    return any(not rest for _, _, rest in events)


def _measure_kind(left, right) -> str | None:
    if not _plays(left) or [(d, rest) for d, _, rest in left] != [(d, rest) for d, _, rest in right]:
        return None
    pitches = [(a, b) for (_, a, rest), (_, b, _) in zip(left, right) if not rest]
    if len(pitches) >= 2 and all(a is not None and b is not None for a, b in pitches):
        intervals = [(a2 - a1, b2 - b1) for (a1, b1), (a2, b2) in zip(pitches, pitches[1:])]
        if sum(1 for x, y in intervals if x == y) / len(intervals) >= LINE_INTERVAL_SHARE:
            return "line"
    return "rhythm"


def _pair_kind(left: dict, right: dict) -> str | None:
    active = [number for number in sorted(set(left) | set(right))
              if _plays(left.get(number, [])) or _plays(right.get(number, []))]
    if not active:
        return None
    kinds = [_measure_kind(left.get(number, []), right.get(number, [])) for number in active]
    if sum(1 for kind in kinds if kind) / len(active) < SHARED_MEASURE_SHARE:
        return None
    return "line" if kinds.count("line") / len(active) >= SHARED_MEASURE_SHARE else "rhythm"


def find_common_lines(score: Score, critical_parts: Iterable[str], first: int, last: int) -> list[CommonLine]:
    """Groups of parts that play the same thing in measures first..last and include a critical part.

    Every part of the score is compared, so a line gathers everyone who plays it even if only one
    of them was flagged as difficult. A group is a "line" only when all its pairs share the line.
    """
    measures = {part.name: _measures(part, first, last) for part in score.parts}
    names = [name for name, bars in measures.items() if any(_plays(events) for events in bars.values())]
    parent = {name: name for name in names}

    def root(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    edges = {}
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            kind = _pair_kind(measures[left], measures[right])
            if kind:
                edges[(left, right)] = kind
                parent[root(left)] = root(right)
    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(root(name), []).append(name)
    critical = set(critical_parts)
    lines = []
    for members in groups.values():
        if len(members) < 2 or not critical & set(members):
            continue
        member_set = set(members)
        kinds = [kind for (left, right), kind in edges.items() if left in member_set and right in member_set]
        lines.append(CommonLine(tuple(sorted(members)), "line" if all(kind == "line" for kind in kinds) else "rhythm"))
    return sorted(lines, key=lambda line: (-len(line.parts), line.parts))
