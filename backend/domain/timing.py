"""Musical timing of the parsed events: what is an attack, the bar length and each voice's line.

A chord is one attack, a continued or stopped tie is not an attack and a grace note is an extra
one. Each voice of a staff is one player, so a bar is as busy as its busiest voice (decided
2026-10-05).
"""
from __future__ import annotations

from collections import defaultdict


def is_attack(event) -> bool:
    return not event.is_rest and event.tie not in ("continue", "stop")


def _by_voice(events) -> dict:
    voices = defaultdict(list)
    for event in events:
        voices[event.voice].append(event)
    return voices


def attack_count(measure) -> int:
    return max((sum(1 for event in events if is_attack(event)) for events in _by_voice(measure.notes).values()),
               default=0)


def measure_length(measure) -> float:
    """The written bar length, else the longest voice."""
    if measure.duration_quarters:
        return measure.duration_quarters
    return max((sum(event.duration_quarters for event in events) for events in _by_voice(measure.notes).values()),
               default=0.0)


def melodic_lines(measures) -> dict:
    """Attacked pitches of each voice in time order across the measures (top note of chords)."""
    lines = defaultdict(list)
    for measure in measures:
        for voice, events in _by_voice(measure.notes).items():
            ordered = sorted(enumerate(events), key=lambda item: (
                item[1].offset_quarters if item[1].offset_quarters is not None else 0.0, item[0]))
            lines[voice].extend(event.pitch for _, event in ordered if is_attack(event) and event.pitch)
    return dict(lines)


def sounding_pitches(event) -> tuple[str, ...]:
    """Every written pitch the event plays: all the notes of a chord."""
    if event.is_rest or event.pitch is None:
        return ()
    return event.chord_pitches or (event.pitch,)


# Default when a score writes no tempo: the crotchet = 120 the audio and the reports also assume.
DEFAULT_QUARTER_BPM = 120.0


def quarter_bpm_at(marks, number: int):
    """Tempo in force at the start of a measure, in quarter notes per minute (None without marks)."""
    current = None
    for mark in sorted(marks, key=lambda mark: (mark.measure_number, mark.offset_quarters)):
        if mark.measure_number > number:
            break
        current = mark.beats_per_minute * mark.beat_unit_quarters
    return current


def notes_per_second(measure, bpm) -> float:
    """Attacks of the busiest voice per second at the given tempo."""
    attacks = attack_count(measure)
    quarters = measure_length(measure)
    if not bpm or not quarters:
        return 0.0
    return attacks / (quarters * 60.0 / bpm)
