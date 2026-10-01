"""Build a sounding-pitch timeline without changing the analysis domain."""
from collections import Counter
import re

from music21 import chord, converter, note, stream, tempo


def build_playback(source, instrument_name: str, first: int, last: int) -> dict:
    score = converter.parse(str(source), format="musicxml")
    raw_names = [part.partName or (part.id if isinstance(part.id, str) else f"Part {i}")
                 for i, part in enumerate(score.parts, 1)]
    counts, indexes = Counter(raw_names), Counter()
    selected = None
    for part, name in zip(score.parts, raw_names):
        if counts[name] > 1:
            indexes[name] += 1
            staff = re.search(r"-Staff(\d+)$", str(part.id))
            name = f"{name} {int(staff.group(1)) if staff else indexes[name]}"
        if name == instrument_name:
            selected = part
            break
    if selected is None:
        raise ValueError("No se encontró el instrumento en la partitura.")

    measures = list(selected.getElementsByClass(stream.Measure))
    chosen = [m for i, m in enumerate(measures, 1) if first <= int(m.number or i) <= last]
    if not chosen:
        raise ValueError("El rango no contiene compases de este instrumento.")
    start = float(chosen[0].offset)
    final_index = measures.index(chosen[-1])
    end = (float(measures[final_index + 1].offset) if final_index + 1 < len(measures)
           else float(selected.highestTime))

    # Tempo directions may be present only in another part of the score.
    marks = {float(mark.getOffsetInHierarchy(score)): float(mark.getQuarterBPM())
             for mark in score.recurse().getElementsByClass(tempo.MetronomeMark)
             if mark.number is not None and mark.getQuarterBPM() > 0}
    boundaries = sorted({0.0: 120.0, **marks}.items())

    def seconds_at(position):
        seconds = 0.0
        for i, (offset, bpm) in enumerate(boundaries):
            stop = boundaries[i + 1][0] if i + 1 < len(boundaries) else position
            if position <= offset:
                break
            seconds += (min(position, stop) - offset) * 60.0 / bpm
        return seconds

    origin = seconds_at(start)
    sounding = selected.toSoundingPitch(inPlace=False).stripTies(inPlace=False)
    events = []
    skipped = 0
    for event in sounding.flatten().notes:
        onset = float(event.offset)
        release = onset + float(event.duration.quarterLength)
        if onset >= end or release <= start:
            continue
        if isinstance(event, note.Unpitched):
            skipped += 1
            continue
        pitches = event.pitches if isinstance(event, chord.Chord) else (event.pitch,)
        for pitch in pitches:
            events.append({
                "note": float(pitch.midi),
                "time": round(seconds_at(max(start, onset)) - origin, 6),
                "duration": round(seconds_at(min(end, release)) - seconds_at(max(start, onset)), 6),
            })
    if len(events) > 10000:
        raise ValueError("El pasaje es demasiado largo para reproducirlo.")
    program = selected.getInstrument().midiProgram
    return {
        "instrument": instrument_name,
        "program": program,
        "events": events,
        "duration": round(seconds_at(end) - origin, 6),
        "default_tempo": not any(offset <= start for offset in marks),
        "skipped_unpitched": skipped,
    }
