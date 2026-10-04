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
class SharedMaterial:
    parts: tuple[str, str]
    kind: str  # "unison", "octave" or "rhythm"


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


def _events(part: ScorePart, first: int, last: int) -> list[tuple[float, int | None, bool]]:
    """(duration, sounding MIDI or None, is_rest) for every event in the measure window."""
    transposition = part.metadata.transposition
    shift = transposition.chromatic + 12 * transposition.octave_change if transposition else 0
    events = []
    for measure in part.measures:
        if first <= measure.number <= last:
            for note in measure.notes:
                sounding = None if note.is_rest or note.pitch is None else m21_pitch.Pitch(note.pitch).midi + shift
                events.append((note.duration_quarters, sounding, note.is_rest))
    return events


def _shared_kind(left, right) -> str | None:
    if not left or [(d, rest) for d, _, rest in left] != [(d, rest) for d, _, rest in right]:
        return None
    played = [(a, b) for (_, a, rest), (_, b, _) in zip(left, right) if not rest]
    if len(played) < 2:
        return None
    if all(a is not None and a == b for a, b in played):
        return "unison"
    if all(a is not None and b is not None for a, b in played) and len({a - b for a, b in played}) == 1 \
            and (played[0][0] - played[0][1]) % 12 == 0:
        return "octave"
    return "rhythm"


def find_shared_material(score: Score, parts: Iterable[str], first: int, last: int) -> tuple[SharedMaterial, ...]:
    """Compare each listed part with every other part of the score in measures first..last."""
    events = {part.name: _events(part, first, last) for part in score.parts}
    found = set()
    for name in parts:
        for other in events:
            if other == name or name not in events:
                continue
            kind = _shared_kind(events[name], events[other])
            if kind:
                found.add(SharedMaterial(tuple(sorted((name, other))), kind))
    return tuple(sorted(found, key=lambda shared: (shared.parts, shared.kind)))
