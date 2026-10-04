"""Melodic phrase boundaries, from the author's criteria (2026-10-04).

Several hints add up and none decides alone, following the cautions of the author:
- a relevant pause: a rest long compared with the local rhythm and with the surrounding rests
  (a short or recurring rest belongs to the motive or to an accompaniment pattern);
- a lengthened note: alone it does not end a phrase (it may sit in the middle), but followed by a
  pause or by a restart of the opening motive it does;
- written breath marks, caesuras and fermatas;
- a restart of the phrase's opening pattern (rhythm and intervals) after a possible ending.
A phrase covers the measures of its notes, so an upbeat stays with the phrase it starts, and a long
phrase is never cut. Harmonic cadences are not analysed yet; a change of pattern is not a boundary
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


def _timeline(part: ScorePart) -> tuple[list[_Note], list[float]]:
    """Sounding notes in time order (simultaneous onsets merged) and onsets of marked rests."""
    notes, marked_rests, start = [], [], 0.0
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
        start += measure.duration_quarters or length
    merged: dict[float, _Note] = {}
    for note in notes:
        current = merged.get(note.onset)
        if current is None or note.duration > current.duration:
            merged[note.onset] = note
    return [merged[onset] for onset in sorted(merged)], marked_rests


def _pattern(notes: list[_Note], index: int):
    window = notes[index:index + PATTERN_NOTES]
    if len(window) < PATTERN_NOTES or any(note.midi is None for note in window):
        return None
    return (tuple(note.duration for note in window),
            tuple(right.midi - left.midi for left, right in zip(window, window[1:])))


def find_phrases(part: ScorePart) -> list[Phrase]:
    notes, marked_rests = _timeline(part)
    if not notes:
        return []
    gaps, sounding = [], notes[0].onset
    for current, following in zip(notes, notes[1:]):
        sounding = max(sounding, current.onset + current.duration)
        gaps.append(max(0.0, following.onset - sounding))
    phrases, phrase_start = [], 0
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
        if current.mark or any(following.onset - gap <= onset < following.onset for onset in marked_rests):
            score += 2
        opening = _pattern(notes, phrase_start)
        if opening is not None and index + 1 > phrase_start + PATTERN_NOTES - 1 and _pattern(notes, index + 1) == opening:
            score += 1
        if score >= BOUNDARY_SCORE:
            phrases.append(Phrase(notes[phrase_start].measure, current.measure))
            phrase_start = index + 1
    phrases.append(Phrase(notes[phrase_start].measure, notes[-1].measure))
    return phrases
