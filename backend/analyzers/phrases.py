"""Melodic phrase boundaries, from the author's criteria (2026-10-04).

Several hints add up and none decides alone, following the cautions of the author:
- a relevant pause: a rest long compared with the local rhythm and with the surrounding rests
  (a short or recurring rest belongs to the motive or to an accompaniment pattern);
- a lengthened note: alone it does not end a phrase (it may sit in the middle), but followed by a
  pause or by a restart of the opening motive it does;
- written breath marks, caesuras and fermatas;
- a restart of the phrase's opening pattern (rhythm and intervals) after a possible ending.
A phrase covers the measures of its notes, so an upbeat stays with the phrase it starts, and a long
phrase is never cut. Short fragments separated by weak boundaries join into phrases of 4 or 8
measures (author's decision); a whole measure of rest or a written mark is a strong boundary that
never joins. Harmonic cadences are not analysed yet; a change of pattern is not a boundary
because it may only be a subdivision.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from music21 import pitch as m21_pitch

from backend.domain.models import ScorePart

BOUNDARY_SCORE = 2
RELEVANT_PAUSE_RATIO = 1.5    # rest at least 1.5 times the typical note of the phrase...
MIN_PAUSE_QUARTERS = 0.5      # ...and never shorter than an eighth note
LENGTHENING_RATIO = 2.0       # a note at least twice the typical previous note
LOCAL_NOTES = 8               # notes that define the local rhythm and the surrounding rests
STANDS_OUT_RATIO = 1.5        # a pause must exceed the surrounding rests by this factor
PATTERN_NOTES = 3             # notes compared to recognise a restart of the opening motive
MIN_PHRASE_MEASURES = 4       # fragments join until a phrase has at least 4 measures...
FULL_PHRASE_MEASURES = 8      # ...or exactly 8 when one more fragment completes it


@dataclass(frozen=True)
class Phrase:
    first_measure: int
    last_measure: int


@dataclass(frozen=True)
class _Note:
    onset: float
    duration: float
    midi: int | None
    measure: int
    mark: bool


def _timeline(part: ScorePart) -> tuple[list[_Note], list[float], dict[int, float]]:
    """Sounding notes in time order (simultaneous onsets merged), onsets of marked rests and bar lengths."""
    notes, marked_rests, start, bar_lengths = [], [], 0.0, {}
    for measure in part.measures:
        position, length = 0.0, 0.0
        for event in measure.notes:
            offset = event.offset_quarters if event.offset_quarters is not None else position
            onset = start + offset
            length = max(length, offset + event.duration_quarters)
            position = offset + event.duration_quarters
            if event.is_rest:
                if event.phrase_mark:
                    marked_rests.append(onset)
                continue
            midi = m21_pitch.Pitch(event.pitch).midi if event.pitch else None
            notes.append(_Note(onset, event.duration_quarters, midi, measure.number, event.phrase_mark))
        bar_lengths[measure.number] = measure.duration_quarters or length
        start += bar_lengths[measure.number]
    merged: dict[float, _Note] = {}
    for note in notes:
        current = merged.get(note.onset)
        if current is None or note.duration > current.duration:
            merged[note.onset] = note
    return [merged[onset] for onset in sorted(merged)], marked_rests, bar_lengths


def _pattern(notes: list[_Note], index: int):
    window = notes[index:index + PATTERN_NOTES]
    if len(window) < PATTERN_NOTES or any(note.midi is None for note in window):
        return None
    return (tuple(note.duration for note in window),
            tuple(right.midi - left.midi for left, right in zip(window, window[1:])))


def find_phrases(part: ScorePart) -> list[Phrase]:
    notes, marked_rests, bar_lengths = _timeline(part)
    if not notes:
        return []
    gaps, sounding = [], notes[0].onset
    for current, following in zip(notes, notes[1:]):
        sounding = max(sounding, current.onset + current.duration)
        gaps.append(max(0.0, following.onset - sounding))
    fragments, phrase_start = [], 0
    for index in range(len(notes) - 1):
        current, following, gap = notes[index], notes[index + 1], gaps[index]
        previous = [note.duration for note in notes[max(phrase_start, index - LOCAL_NOTES):index]]
        typical = median(previous) if previous else current.duration
        score = 0
        around = [value for value in gaps[max(0, index - LOCAL_NOTES):index] + gaps[index + 1:index + 1 + LOCAL_NOTES] if value > 0]
        stands_out = not around or gap >= STANDS_OUT_RATIO * median(around)
        if gap >= max(RELEVANT_PAUSE_RATIO * typical, MIN_PAUSE_QUARTERS) and stands_out:
            score += 2
        lengthened = bool(previous) and current.duration >= LENGTHENING_RATIO * typical
        if lengthened:
            score += 1 + (1 if gap > 0 else 0)
        marked = current.mark or any(following.onset - gap <= onset < following.onset for onset in marked_rests)
        if marked:
            score += 2
        opening = _pattern(notes, phrase_start)
        if opening is not None and index + 1 > phrase_start + PATTERN_NOTES - 1 and _pattern(notes, index + 1) == opening:
            score += 1
        if score >= BOUNDARY_SCORE:
            strong = marked or gap >= bar_lengths.get(current.measure, 4.0)
            fragments.append((notes[phrase_start].measure, current.measure, strong))
            phrase_start = index + 1
    fragments.append((notes[phrase_start].measure, notes[-1].measure, True))
    return _join_fragments(fragments)


def _join_fragments(fragments: list[tuple[int, int, bool]]) -> list[Phrase]:
    """Join fragments across weak boundaries until a phrase has 4 or 8 measures (from 5 to 7, one more
    fragment is joined only when it completes exactly 8); strong boundaries always end the phrase."""
    phrases, index = [], 0
    while index < len(fragments):
        first, last, strong = fragments[index]
        index += 1
        while not strong and index < len(fragments):
            length = last - first + 1
            next_first, next_last, next_strong = fragments[index]
            joined = next_last - first + 1
            # Close at 4 or 8 measures; from 5 to 7, join only when one more fragment completes 8.
            completes_eight = MIN_PHRASE_MEASURES < length < FULL_PHRASE_MEASURES and joined == FULL_PHRASE_MEASURES
            if length >= MIN_PHRASE_MEASURES and not completes_eight:
                break
            last, strong = next_last, next_strong
            index += 1
        phrases.append(Phrase(first, last))
    return phrases
