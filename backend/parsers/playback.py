"""Sounding-pitch timelines for solo passages and the full ensemble."""
from collections import Counter, OrderedDict
from hashlib import sha256
import os
import re
from threading import Lock

from pathlib import Path

from music21 import chord, converter, note, percussion as m21_percussion, stream, tempo

from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import ScorePart
from backend.parsers.musicxml_parser import metadata_for_part, read_part_metadata
from backend.parsers.musicxml_source import extract_musicxml


def _drum_note(hit, part, name):
    """General MIDI percussion key of a hit, from its instrument or, failing that, the part name."""
    inst = getattr(hit, 'storedInstrument', None) or part.getInstrument()
    drum = getattr(inst, 'percMapPitch', None)
    if drum is None:
        lower_name = name.casefold()
        drum = next((number for text, number in (
            ('snare', 38), ('bass drum', 35), ('tambourine', 54),
            ('triangle', 81), ('cymbal', 49), ('hi-hat', 42), ('tom', 45)
        ) if text in lower_name), None)
    return drum


def _identity(part, name, declared):
    return resolve_part(ScorePart(name, (), metadata_for_part(part, declared))).identity


# Passages of the same work reuse the parsed score (2026-10-07: parsing a real band score took most of
# the 10-20 s the author waited per passage). Keyed by content, so each request's temporary file name
# does not matter; the timeline never modifies the score (it works on copies of each part).
# A parsed band score can take ~100-200 MB: small servers keep fewer (Render's free plan: 1).
def _scores_kept() -> int:
    try:
        return max(1, int(os.environ.get('PLAYBACK_SCORES_KEPT', '4')))
    except ValueError:
        return 4


PARSED_SCORES_KEPT = _scores_kept()
_parsed_scores: OrderedDict = OrderedDict()
# One timeline at a time: music21 objects are shared between requests.
_build_lock = Lock()


def clear_parsed_scores() -> None:
    with _build_lock:
        _parsed_scores.clear()


def parsed_score_count() -> int:
    return len(_parsed_scores)


def _parsed_score(content: bytes):
    """Parsed score and declared part metadata of a MusicXML content (the last few kept)."""
    key = sha256(content).hexdigest()
    if key in _parsed_scores:
        _parsed_scores.move_to_end(key)
        return _parsed_scores[key]
    # From the bytes, as the analysis parser: music21 then does not write its own cache to disk.
    parsed = (converter.parse(content, format='musicxml'), read_part_metadata(content))
    _parsed_scores[key] = parsed
    while len(_parsed_scores) > PARSED_SCORES_KEPT:
        _parsed_scores.popitem(last=False)
    return parsed


def build_playback(source, instrument_name, first: int, last: int) -> dict:
    """Timeline for one part (str), several parts (list: a sectional rehearsal block) or the whole score ('')."""
    with _build_lock:
        return _build_playback(source, instrument_name, first, last)


def _build_playback(source, instrument_name, first: int, last: int) -> dict:
    solo = isinstance(instrument_name, str) and bool(instrument_name)
    wanted = [instrument_name] if isinstance(instrument_name, str) else list(instrument_name or ())
    wanted = [name for name in wanted if name]
    raw = Path(source).read_bytes()
    score, declared = _parsed_score(extract_musicxml(raw) or raw)
    raw_names = [part.partName or (part.id if isinstance(part.id, str) else f'Part {i}')
                 for i, part in enumerate(score.parts, 1)]
    counts, indexes = Counter(raw_names), Counter()
    named_parts = []
    for part, name in zip(score.parts, raw_names):
        if counts[name] > 1:
            indexes[name] += 1
            staff = re.search(r'-Staff(\d+)$', str(part.id))
            name = f'{name} {int(staff.group(1)) if staff else indexes[name]}'
        if not wanted or name in wanted:
            named_parts.append((part, name))
    if not named_parts or len(named_parts) < len(set(wanted)):
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
    if wanted:
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
            # Simultaneous drum-set hits arrive as a PercussionChord, not as chord.Chord.
            hits = (list(event.notes) if isinstance(event, m21_percussion.PercussionChord)
                    else [event] if isinstance(event, note.Unpitched) else [])
            if hits:
                for hit in hits:
                    drum = _drum_note(hit, selected, name)
                    if drum is not None:
                        percussion.append({'note': drum, **timing})
                    else:
                        skipped += 1
                continue
            pitches = event.pitches if isinstance(event, chord.Chord) else (event.pitch,)
            events.extend({'note': float(pitch.midi), **timing} for pitch in pitches)
        total_events += len(events) + len(percussion)
        if total_events > (min(150000, 10000 * len(wanted)) if wanted else 150000):
            raise ValueError('La partitura es demasiado larga para reproducirla.')
        identity = _identity(selected, name, declared)
        tracks.append({'instrument': name, 'program': selected.getInstrument().midiProgram,
                       'canonical_id': identity.canonical_id if identity else None,
                       'sound': identity.sound if identity else None,
                       'events': events, 'percussion': percussion, 'skipped_unpitched': skipped})
    shared = {'duration': round(seconds_at(end) - origin, 6),
              'default_tempo': not any(offset <= start for offset in marks),
              'measures': [{'number': int(m.number or i), 'time': round(seconds_at(float(m.offset)) - origin, 6)}
                           for i, m in enumerate(named_parts[0][0].getElementsByClass(stream.Measure), 1)
                           if start <= float(m.offset) < end],
              'tempo_map': [{'quarter': offset, 'time': seconds_at(offset), 'bpm': bpm}
                            for offset, bpm in boundaries]}
    if solo:
        return {**tracks[0], **shared}
    return {'tracks': tracks, **shared}
