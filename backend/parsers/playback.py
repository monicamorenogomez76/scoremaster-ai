"""Sounding-pitch timelines for solo passages and the full ensemble."""
from collections import Counter, OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeout, wait
from dataclasses import dataclass
import gzip
from hashlib import sha256
import json
import logging
import os
import re
from threading import RLock
from typing import Optional, Protocol

from pathlib import Path

from music21 import chord, converter, note, percussion as m21_percussion, stream, tempo

from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import ScorePart
from backend.parsers.musicxml_parser import metadata_for_part, read_part_metadata
from backend.parsers.musicxml_source import extract_musicxml
from backend.parsers.reader import reader


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


# Each work is read with music21 once: its parts, measures, tempo marks and sounding notes are kept as
# plain numbers, and every passage is cut from them (2026-10-07: parsing a real band score took most of
# the 10-20 s the author waited per passage, and more than a minute on Render's free plan).
# Keyed by content, so each request's temporary file name does not matter. A prepared band score takes
# a few MB, against ~100-200 MB for the parsed score it replaces.
def _scores_kept() -> int:
    try:
        return max(1, int(os.environ.get('PLAYBACK_SCORES_KEPT', '4')))
    except ValueError:
        return 4


# Beyond this the work is too large to keep (the whole-score playback already stops at 150 000 events).
MAX_PREPARED_NOTES = 1_000_000
# Stored timelines of another version are prepared again.
TIMELINE_VERSION = 'playback-timeline-v1'
# A small work is answered in the same request; a longer one answers 202 and the browser follows its
# preparation, so no request stays open for minutes (2026-10-07: Persis took ~3 min on Render).
WAIT_SECONDS = 20.0
FAILURES_KEPT = 16
_timelines: OrderedDict = OrderedDict()
_pending: dict = {}                 # key → Future of a preparation in progress
_failed: OrderedDict = OrderedDict()
_lock = RLock()                     # guards the three dictionaries above
_reader = reader              # shared with the analysis: one music21 reading at a time
logger = logging.getLogger(__name__)


class PreparedStore(Protocol):
    """Prepared works kept across restarts, by content hash and algorithm version."""
    def load(self, key: str, version: str) -> Optional[bytes]: ...
    def save(self, key: str, version: str, data: bytes) -> None: ...


@dataclass(frozen=True)
class _Note:
    onset: float
    release: float
    pitches: tuple = ()      # MIDI numbers of a pitched note or chord
    drums: tuple = ()        # General MIDI keys of percussion hits; None for a hit without one


@dataclass(frozen=True)
class _Part:
    name: str
    program: object
    canonical_id: object
    sound: object
    measures: tuple          # (number, offset) of each measure
    highest_time: float
    notes: tuple


@dataclass(frozen=True)
class _Timeline:
    parts: tuple
    marks: dict              # offset → quarter BPM of each metronome mark
    highest_time: float


def clear_timelines() -> None:
    with _lock:
        _timelines.clear()
        _failed.clear()


def prepared_count() -> int:
    return len(_timelines)


class NotMusicXML(ValueError):
    """The uploaded file is not a MusicXML score."""


class StillPreparing(Exception):
    """The work is being prepared in the background; its key lets the browser follow it."""
    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def preparation_enabled() -> bool:
    """Works are prepared in the background when analysed or opened (PLAYBACK_WARMUP=0 turns it off)."""
    return os.environ.get('PLAYBACK_WARMUP', '1') != '0'


def timeline_key(content: bytes) -> str:
    """Keyed by the uploaded bytes, so a prepared work is cut without validating its XML again."""
    return sha256(content).hexdigest()


def _remember(key: str, timeline: _Timeline) -> None:
    with _lock:
        _timelines[key] = timeline
        _timelines.move_to_end(key)
        while len(_timelines) > _scores_kept():
            _timelines.popitem(last=False)
        _failed.pop(key, None)


def _ready(key: str, store: Optional[PreparedStore]) -> Optional[_Timeline]:
    """A prepared work, from memory or from the store; it never waits for the work being read."""
    with _lock:
        found = _timelines.get(key)
        if found is not None:
            _timelines.move_to_end(key)
            return found
    if store is None:
        return None
    try:
        data = store.load(key, TIMELINE_VERSION)
        found = _decode(data) if data else None
    except Exception:
        logger.warning('No se pudo leer el audio preparado de una obra.', exc_info=True)
        return None
    if found is not None:
        _remember(key, found)
    return found


def _prepare(content: bytes, key: str, store: Optional[PreparedStore]) -> _Timeline:
    """Runs in the reader thread."""
    found = _ready(key, store)
    if found is not None:
        return found
    source = extract_musicxml(content)
    if source is None:
        raise NotMusicXML('La partitura no es MusicXML válido.')
    found = _read_timeline(source)
    if store is not None:
        try:
            store.save(key, TIMELINE_VERSION, _encode(found))
        except Exception:
            logger.warning('No se pudo guardar el audio preparado de una obra.', exc_info=True)
    _remember(key, found)
    return found


def _finished(key: str, future: Future) -> None:
    with _lock:
        _pending.pop(key, None)
        if future.cancelled() or future.exception() is not None:
            _failed[key] = True
            while len(_failed) > FAILURES_KEPT:
                _failed.popitem(last=False)


def start_preparation(content: bytes, store: Optional[PreparedStore] = None) -> Future:
    """The preparation of a work, started now unless it is already in progress."""
    key = timeline_key(content)
    with _lock:
        future = _pending.get(key)
        if future is None:
            future = _reader.submit(_prepare, content, key, store)
            _pending[key] = future
            future.add_done_callback(lambda done: _finished(key, done))
        return future


def preparation_status(key: str) -> str:
    with _lock:
        if key in _timelines:
            return 'ready'
        if key in _pending:
            return 'preparing'
        return 'failed' if key in _failed else 'unknown'


def wait_for_preparations() -> None:
    with _lock:
        futures = list(_pending.values())
    wait(futures)


def prepare_playback(content: bytes, store: Optional[PreparedStore] = None) -> None:
    """Read a work ahead of its first passage; called in the background, so failures are only logged."""
    try:
        start_preparation(content, store).result()
    except Exception:
        logger.warning('No se pudo preparar el audio de una obra.', exc_info=True)


def _timeline(content: bytes, store: Optional[PreparedStore], answer_quickly: bool) -> _Timeline:
    key = timeline_key(content)
    found = _ready(key, store)
    if found is not None:
        return found
    future = start_preparation(content, store)
    try:
        return future.result(timeout=WAIT_SECONDS if answer_quickly else None)
    except FutureTimeout:
        raise StillPreparing(key) from None


def _encode(timeline: _Timeline) -> bytes:
    return gzip.compress(json.dumps({
        'parts': [[part.name, part.program, part.canonical_id, part.sound, part.measures, part.highest_time,
                   [[item.onset, item.release, item.pitches, item.drums] for item in part.notes]]
                  for part in timeline.parts],
        'marks': list(timeline.marks.items()),
        'highest_time': timeline.highest_time,
    }).encode())


def _decode(data: bytes) -> _Timeline:
    raw = json.loads(gzip.decompress(data))
    parts = tuple(_Part(name, program, canonical_id, sound, tuple((number, offset) for number, offset in measures),
                        highest_time, tuple(_Note(onset, release, tuple(pitches), tuple(drums))
                                            for onset, release, pitches, drums in notes))
                  for name, program, canonical_id, sound, measures, highest_time, notes in raw['parts'])
    return _Timeline(parts, {offset: bpm for offset, bpm in raw['marks']}, raw['highest_time'])


def _read_timeline(content: bytes) -> _Timeline:
    # From the bytes, as the analysis parser: music21 then does not write its own cache to disk.
    score = converter.parse(content, format='musicxml')
    declared = read_part_metadata(content)
    raw_names = [part.partName or (part.id if isinstance(part.id, str) else f'Part {i}')
                 for i, part in enumerate(score.parts, 1)]
    counts, indexes = Counter(raw_names), Counter()
    parts, total = [], 0
    for part, name in zip(score.parts, raw_names):
        if counts[name] > 1:
            indexes[name] += 1
            staff = re.search(r'-Staff(\d+)$', str(part.id))
            name = f'{name} {int(staff.group(1)) if staff else indexes[name]}'
        # Everything read from the written part comes first: the score is then changed in place, which
        # saves the deep copies that took two thirds of the time (nobody else uses this parsed score).
        identity = _identity(part, name, declared)
        program = part.getInstrument().midiProgram
        measures = tuple((int(m.number or i), float(m.offset))
                         for i, m in enumerate(part.getElementsByClass(stream.Measure), 1))
        highest_time = float(part.highestTime)
        part.toSoundingPitch(inPlace=True)
        part.stripTies(inPlace=True)
        notes = []
        for event in part.flatten().notes:
            onset = float(event.offset)
            release = onset + float(event.duration.quarterLength)
            # Simultaneous drum-set hits arrive as a PercussionChord, not as chord.Chord.
            hits = (list(event.notes) if isinstance(event, m21_percussion.PercussionChord)
                    else [event] if isinstance(event, note.Unpitched) else [])
            if hits:
                notes.append(_Note(onset, release, drums=tuple(_drum_note(hit, part, name) for hit in hits)))
            else:
                pitches = event.pitches if isinstance(event, chord.Chord) else (event.pitch,)
                notes.append(_Note(onset, release, pitches=tuple(float(pitch.midi) for pitch in pitches)))
        total += len(notes)
        if total > MAX_PREPARED_NOTES:
            raise ValueError('La partitura es demasiado larga para reproducirla.')
        parts.append(_Part(name, program, identity.canonical_id if identity else None,
                           identity.sound if identity else None, measures, highest_time, tuple(notes)))
    marks = {float(mark.getOffsetInHierarchy(score)): float(mark.getQuarterBPM())
             for mark in score.recurse().getElementsByClass(tempo.MetronomeMark)
             if mark.number is not None and mark.getQuarterBPM() > 0}
    return _Timeline(tuple(parts), marks, float(score.highestTime))


def build_playback(source, instrument_name, first: int, last: int, store: Optional[PreparedStore] = None,
                   answer_quickly: bool = False) -> dict:
    """Timeline for one part (str), several parts (list: a sectional rehearsal block) or the whole score ('').

    The source is the uploaded file's bytes or a path to it. With answer_quickly, a work that takes
    longer than WAIT_SECONDS to prepare raises StillPreparing while its preparation goes on."""
    content = source if isinstance(source, bytes) else Path(source).read_bytes()
    return _cut(_timeline(content, store, answer_quickly), instrument_name, first, last)


def _cut(timeline: _Timeline, instrument_name, first: int, last: int) -> dict:
    solo = isinstance(instrument_name, str) and bool(instrument_name)
    wanted = [instrument_name] if isinstance(instrument_name, str) else list(instrument_name or ())
    wanted = [name for name in wanted if name]
    named_parts = [part for part in timeline.parts if not wanted or part.name in wanted]
    if not named_parts or len(named_parts) < len(set(wanted)):
        raise ValueError('No se encontró el instrumento en la partitura.')

    marks = timeline.marks
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
    start, end = 0.0, timeline.highest_time
    if wanted:
        selected = named_parts[0]
        measures = selected.measures
        chosen = [i for i, (number, _) in enumerate(measures) if first <= number <= last]
        if not chosen:
            raise ValueError('El rango no contiene compases de este instrumento.')
        start = measures[chosen[0]][1]
        end = measures[chosen[-1] + 1][1] if chosen[-1] + 1 < len(measures) else selected.highest_time
    origin = seconds_at(start)
    tracks = []
    total_events = 0
    for selected in named_parts:
        events, percussion, skipped = [], [], 0
        for event in selected.notes:
            if event.onset >= end or event.release <= start:
                continue
            timing = {'time': round(seconds_at(max(start, event.onset)) - origin, 6),
                      'duration': round(seconds_at(min(end, event.release)) - seconds_at(max(start, event.onset)), 6)}
            if event.drums:
                for drum in event.drums:
                    if drum is not None:
                        percussion.append({'note': drum, **timing})
                    else:
                        skipped += 1
                continue
            events.extend({'note': pitch, **timing} for pitch in event.pitches)
        total_events += len(events) + len(percussion)
        if total_events > (min(150000, 10000 * len(wanted)) if wanted else 150000):
            raise ValueError('La partitura es demasiado larga para reproducirla.')
        tracks.append({'instrument': selected.name, 'program': selected.program,
                       'canonical_id': selected.canonical_id, 'sound': selected.sound,
                       'events': events, 'percussion': percussion, 'skipped_unpitched': skipped})
    shared = {'duration': round(seconds_at(end) - origin, 6),
              'default_tempo': not any(offset <= start for offset in marks),
              'measures': [{'number': number, 'time': round(seconds_at(offset) - origin, 6)}
                           for number, offset in named_parts[0].measures
                           if start <= offset < end],
              'tempo_map': [{'quarter': offset, 'time': seconds_at(offset), 'bpm': bpm}
                            for offset, bpm in boundaries]}
    if solo:
        return {**tracks[0], **shared}
    return {'tracks': tracks, **shared}
