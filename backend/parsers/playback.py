"""Sounding-pitch timelines for solo passages and the full ensemble."""
from collections import Counter
import re

from music21 import chord, converter, note, stream, tempo


def build_playback(source, instrument_name: str, first: int, last: int) -> dict:
    score = converter.parse(str(source), format='musicxml')
    raw_names = [part.partName or (part.id if isinstance(part.id, str) else f'Part {i}')
                 for i, part in enumerate(score.parts, 1)]
    counts, indexes = Counter(raw_names), Counter()
    named_parts = []
    for part, name in zip(score.parts, raw_names):
        if counts[name] > 1:
            indexes[name] += 1
            staff = re.search(r'-Staff(\d+)$', str(part.id))
            name = f'{name} {int(staff.group(1)) if staff else indexes[name]}'
        if not instrument_name or name == instrument_name:
            named_parts.append((part, name))
    if not named_parts:
        raise ValueError('No se encontró el instrumento en la partitura.')

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

    # Whole-score playback shares one origin, even when some parts start later.
    start, end = 0.0, float(score.highestTime)
    if instrument_name:
        selected = named_parts[0][0]
        measures = list(selected.getElementsByClass(stream.Measure))
        chosen = [m for i, m in enumerate(measures, 1) if first <= int(m.number or i) <= last]
        if not chosen:
            raise ValueError('El rango no contiene compases de este instrumento.')
        start = float(chosen[0].offset)
        final_index = measures.index(chosen[-1])
        end = (float(measures[final_index + 1].offset) if final_index + 1 < len(measures)
               else float(selected.highestTime))
    origin = seconds_at(start)
    tracks = []
    total_events = 0
    for selected, name in named_parts:
        sounding = selected.toSoundingPitch(inPlace=False).stripTies(inPlace=False)
        events, percussion, skipped = [], [], 0
        for event in sounding.flatten().notes:
            onset = float(event.offset)
            release = onset + float(event.duration.quarterLength)
            if onset >= end or release <= start:
                continue
            timing = {'time': round(seconds_at(max(start, onset)) - origin, 6),
                      'duration': round(seconds_at(min(end, release)) - seconds_at(max(start, onset)), 6)}
            if isinstance(event, note.Unpitched):
                inst = event.storedInstrument or selected.getInstrument()
                drum = getattr(inst, 'percMapPitch', None)
                if drum is None:
                    lower_name = name.casefold()
                    drum = next((number for text, number in (
                        ('snare', 38), ('bass drum', 35), ('tambourine', 54),
                        ('triangle', 81), ('cymbal', 49), ('hi-hat', 42), ('tom', 45)
                    ) if text in lower_name), None)
                if drum is not None:
                    percussion.append({'note': drum, **timing})
                else:
                    skipped += 1
                continue
            pitches = event.pitches if isinstance(event, chord.Chord) else (event.pitch,)
            events.extend({'note': float(pitch.midi), **timing} for pitch in pitches)
        total_events += len(events) + len(percussion)
        if total_events > (10000 if instrument_name else 150000):
            raise ValueError('La partitura es demasiado larga para reproducirla.')
        tracks.append({'instrument': name, 'program': selected.getInstrument().midiProgram,
                       'events': events, 'percussion': percussion, 'skipped_unpitched': skipped})
    shared = {'duration': round(seconds_at(end) - origin, 6),
              'default_tempo': not any(offset <= start for offset in marks),
              'measures': [{'number': int(m.number or i), 'time': seconds_at(float(m.offset))}
                           for i, m in enumerate(named_parts[0][0].getElementsByClass(stream.Measure), 1)],
              'tempo_map': [{'quarter': offset, 'time': seconds_at(offset), 'bpm': bpm}
                            for offset, bpm in boundaries]}
    if instrument_name:
        return {**tracks[0], **shared}
    return {'tracks': tracks, **shared}
