"""Harmonic cadences of the whole ensemble, for phrase endings (criteria of 2026-10-04).

The melody ending on the tonic is not enough: the accompaniment decides. Every pitched part is read
in sounding pitch (declared transposition) and the key of each measure is estimated from the
surrounding measures (Krumhansl-Kessler profiles). A cadence is an arrival on a strong beat:
- authentic: the dominant (bass on the dominant, with the leading tone) moves to the tonic (bass on
  the tonic);
- half: the dominant arrives after other harmony, is held at least two beats and does not resolve
  to the tonic.
Chords written inside one staff are not read by the parser yet; band parts carry one voice each.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from music21 import pitch as m21_pitch

from backend.domain.models import Score, ScorePart

MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
KEY_CONTEXT_MEASURES = 4    # the key of a measure comes from the measures around it
CHORD_SHARE = 0.75          # share of the sounding notes that must belong to the chord
HALF_CADENCE_BEATS = 2.0    # a half cadence holds the dominant at least this long


@dataclass(frozen=True)
class _Event:
    start: float
    end: float
    midi: int
    measure: int


def _part_events(part: ScorePart) -> tuple[list[_Event], dict[int, tuple[float, float]]]:
    """Sounding notes on the part's time line and (start, length) of each measure."""
    transposition = part.metadata.transposition
    shift = transposition.chromatic + 12 * transposition.octave_change if transposition else 0
    events, measures, start = [], {}, 0.0
    for measure in part.measures:
        position, length = 0.0, 0.0
        for note in measure.notes:
            offset = note.offset_quarters if note.offset_quarters is not None else position
            position = offset + note.duration_quarters
            length = max(length, position)
            if not note.is_rest and note.pitch:
                events.append(_Event(start + offset, start + position, m21_pitch.Pitch(note.pitch).midi + shift,
                                     measure.number))
        length = measure.duration_quarters or length
        measures[measure.number] = (start, length)
        start += length
    return events, measures


def _correlation(left, right) -> float:
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    spread = (sum((a - mean_left) ** 2 for a in left) * sum((b - mean_right) ** 2 for b in right)) ** 0.5
    return covariance / spread if spread else 0.0


def _key(histogram: list[float]) -> tuple[int, bool]:
    """(tonic pitch class, is_minor) whose profile best matches the duration-weighted pitch classes."""
    best, best_value = (0, False), float("-inf")
    for minor, profile in ((False, MAJOR_PROFILE), (True, MINOR_PROFILE)):
        for tonic in range(12):
            value = _correlation(histogram, [profile[(pc - tonic) % 12] for pc in range(12)])
            if value > best_value + 1e-9:
                best, best_value = (tonic, minor), value
    return best


def _function(midis: list[int], tonic: int, minor: bool) -> str | None:
    """"I", "V" or "other" for the notes sounding together."""
    if not midis:
        return None
    bass = min(midis) % 12
    classes = [midi % 12 for midi in midis]
    dominant = (tonic + 7) % 12
    tonic_chord = {tonic, (tonic + 3) % 12, (tonic + 4) % 12, dominant}
    dominant_chord = {dominant, (dominant + 4) % 12, (dominant + 7) % 12, (dominant + 10) % 12}

    def fits(chord):
        return sum(1 for pc in classes if pc in chord) / len(classes) >= CHORD_SHARE
    if bass == tonic and fits(tonic_chord):
        return "I"
    if bass == dominant and (dominant + 4) % 12 in classes and fits(dominant_chord):
        return "V"
    return "other"


def find_cadences(score: Score) -> dict[tuple[int, float], str]:
    """(measure, offset in the measure) of each cadential arrival → "authentic" or "half"."""
    events, measures = [], {}
    for part in score.parts:
        part_events, part_measures = _part_events(part)
        events.extend(part_events)
        for number, bounds in part_measures.items():
            measures.setdefault(number, bounds)
    if not events:
        return {}
    numbers = sorted(measures, key=lambda number: measures[number][0])
    histograms = {number: [0.0] * 12 for number in numbers}
    for event in events:
        histograms[event.measure][event.midi % 12] += event.end - event.start
    keys = {}
    for index, number in enumerate(numbers):
        window = numbers[max(0, index - KEY_CONTEXT_MEASURES):index + KEY_CONTEXT_MEASURES + 1]
        keys[number] = _key([sum(histograms[other][pc] for other in window) for pc in range(12)])

    starts = [measures[number][0] for number in numbers]

    def measure_at(time):
        return numbers[max(0, bisect_right(starts, time + 1e-9) - 1)]

    onsets = sorted({event.start for event in events} | {event.end for event in events})
    pending, next_event = sorted(events, key=lambda event: event.start), 0
    active: list[_Event] = []
    slices = []   # (start, end, measure, sounding MIDI notes)
    for start, end in zip(onsets, onsets[1:]):
        while next_event < len(pending) and pending[next_event].start <= start + 1e-9:
            active.append(pending[next_event])
            next_event += 1
        active = [event for event in active if event.end > start + 1e-9]
        slices.append((start, end, measure_at(start), [event.midi for event in active]))

    # The profiles often confuse a key with its relative (G major / E minor): look in both.
    relative = {number: ((tonic + 3) % 12, False) if minor else ((tonic + 9) % 12, True)
                for number, (tonic, minor) in keys.items()}
    found = [_cadences(slices, keys, measures), _cadences(slices, relative, measures)]
    # A closing (authentic) reading wins over a half cadence at the same arrival.
    return {where: "authentic" if any(item.get(where) == "authentic" for item in found) else "half"
            for where in sorted(set(found[0]) | set(found[1]))}


def _cadences(slices, keys, measures) -> dict[tuple[int, float], str]:
    regions: list[dict] = []   # consecutive time slices with the same harmonic function
    for start, end, number, midis in slices:
        function = _function(midis, *keys[number])
        if regions and regions[-1]["function"] == function and abs(regions[-1]["end"] - start) < 1e-9:
            regions[-1]["end"] = end
        else:
            regions.append({"function": function, "start": start, "end": end, "measure": number})

    def strong(region) -> bool:
        measure_start, length = measures[region["measure"]]
        offset = region["start"] - measure_start
        return abs(offset) < 1e-9 or abs(offset - length / 2) < 1e-9

    def where(region):
        return region["measure"], round(region["start"] - measures[region["measure"]][0], 4)

    cadences = {}
    sounding = [region for region in regions if region["function"] is not None]
    for index, region in enumerate(sounding):
        previous = sounding[index - 1] if index else None
        following = sounding[index + 1] if index + 1 < len(sounding) else None
        if not strong(region):
            continue
        if region["function"] == "I" and previous and previous["function"] == "V":
            cadences[where(region)] = "authentic"
        elif (region["function"] == "V" and region["end"] - region["start"] >= HALF_CADENCE_BEATS
              and previous is not None and (following is None or following["function"] != "I")):
            cadences[where(region)] = "half"
    return cadences
