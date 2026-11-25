"""Sounding-pitch timelines for solo passages and the full ensemble."""
from bisect import bisect_left, bisect_right
from collections import Counter, OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeout, wait
from dataclasses import dataclass
import gzip
from hashlib import sha256
import json
import logging
import math
import os
import re
from threading import RLock
from typing import Callable, Optional, Protocol

from pathlib import Path

from music21 import chord, converter, expressions, note, percussion as m21_percussion, stream, tempo

from backend.domain.instrument_catalog import GENERIC_PERCUSSION, identity_by_id, match_instrument_name
from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import ScorePart
from backend.parsers.instrument_changes import note_instruments, note_key, split_name
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


# General MIDI key of each unpitched percussion instrument of the catalog (2026-11-01): copista writes them as pitched
# notes in treble clef, and without a drum the browser played them on its fallback piano.
DRUM_KEYS = {'snare_drum': 38, 'bass_drum': 35, 'crash_cymbals': 49, 'suspended_cymbal': 51, 'tambourine': 54,
             'triangle': 81,
             # The usual percussion of a band (2026-11-21); General MIDI has no gong, castanets, sleigh bells, mark tree,
             # whip or ratchet, which take the nearest sound: Chinese cymbal, claves, tambourine, open triangle, hand clap
             # and short guiro.
             'wood_block': 76, 'temple_blocks': 77, 'tam_tam': 52, 'toms': 45, 'tenor_drum': 47, 'hi_hat': 42,
             'finger_cymbals': 80, 'castanets': 75, 'claves': 75, 'maracas': 70, 'guiro': 73, 'cowbell': 56,
             'cabasa': 69, 'shaker': 70, 'bongos': 60, 'congas': 63, 'vibraslap': 58, 'whistle': 71, 'sleigh_bells': 54,
             'wind_chimes': 81, 'whip': 39, 'ratchet': 73}
# A drum set written with pitches, by the usual positions of drum notation: bass drum F4, snare C5, hi-hat G5, crash A5.
DRUM_SET_KEYS = {65: 36, 64: 36, 72: 38, 71: 38, 79: 42, 81: 49, 76: 45, 74: 47, 77: 43}


def _unpitched_key(identity, midi: float) -> int | None:
    """The drum a pitched note of an unpitched percussion part plays; None for any other part."""
    if identity is None or identity.section != 'percussion' or identity.sound is not None:
        return None
    if identity.canonical_id in ('drum_set', 'percussion'):
        # A part of several instruments by the line they sit on (2026-11-02): low drums, snare, cymbals.
        return DRUM_SET_KEYS.get(int(midi), 45 if midi < 64 else 49 if midi > 78 else 38)
    return DRUM_KEYS.get(identity.canonical_id, 38)


def _identity(part, name, declared):
    return resolve_part(ScorePart(name, (), metadata_for_part(part, declared))).identity


def _changed_identity(instrument: str, identity):
    """One of the instruments of a part that changes; one the catalog does not know (wood blocks, gong) sounds as the
    percussion the part is, by the line its notes sit on."""
    found = match_instrument_name(instrument).identity
    if found is None and identity is not None and identity.section == 'percussion':
        return identity_by_id(GENERIC_PERCUSSION)
    return found or identity


# Each work is read with music21 once: its parts, measures, tempo marks and sounding notes are kept as
# plain numbers, and every passage is cut from them (2026-10-07: parsing a real band score took most of
# the 10-20 s waited per passage, and more than a minute on Render's free plan).
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
TIMELINE_VERSION = 'playback-timeline-v7'   # v7 (2026-11-20): every part keeps the band's measures; v6 (2026-11-20): trills, mordents and turns sound as their notes; v5 (2026-11-17): a part that changes instrument sounds as each one; v4 (2026-11-05): grace notes sound; v3 (2026-11-02): the generic percussion plays drums by line
# A grace note takes no time in the score: it sounds this long, just before its note, which stays on the beat (2026-11-05:
# with no length it fell on the note and could hardly be heard).
GRACE_QUARTERS = 0.125
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


class WorkTooLarge(Exception):
    """The work does not fit in the memory of this server."""


# A work whose MusicXML is at least this long is read outside the server when there is a reader for it (2026-11-25): music21
# takes some forty times the text, and a band of 11 MB without its audio restarted Render (512 MB) with a 502.
LARGE_SOURCE = 2 * 1024 * 1024
_read_large: Optional[Callable[[bytes], bytes]] = None


def read_large_works_with(reader_of_works: Optional[Callable[[bytes], bytes]]) -> None:
    """content → its encoded timeline, in a process of its own; None: every work is read here."""
    global _read_large
    _read_large = reader_of_works


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


def prepared_timeline(content: bytes, store: Optional[PreparedStore]) -> Optional[bytes]:
    """What the store keeps for a work already prepared, never preparing it; None otherwise."""
    found = _ready(timeline_key(content), store)
    return _encode(found) if found is not None else None


def keep_timeline(content: bytes, data: bytes, store: Optional[PreparedStore]) -> None:
    """A timeline made elsewhere for these bytes (a corrected note, 2026-11-22), kept as if it had been prepared here."""
    key = timeline_key(content)
    if store is not None:
        try:
            store.save(key, TIMELINE_VERSION, data)
        except Exception:
            logger.warning('No se pudo guardar el audio preparado de una obra.', exc_info=True)
    _remember(key, _decode(data))


def is_prepared(content: bytes, store: Optional[PreparedStore] = None) -> bool:
    return _ready(timeline_key(content), store) is not None


def _prepare(content: bytes, key: str, store: Optional[PreparedStore]) -> _Timeline:
    """Runs in the reader thread."""
    found = _ready(key, store)
    if found is not None:
        return found
    source = extract_musicxml(content)
    if source is None:
        raise NotMusicXML('La partitura no es MusicXML válido.')
    outside = _read_large(content) if _read_large is not None and len(source) >= LARGE_SOURCE else None
    found = _decode(outside) if outside is not None else _read_timeline(source)
    if store is not None:
        try:
            store.save(key, TIMELINE_VERSION, outside if outside is not None else _encode(found))
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


def encode_timeline(content: bytes) -> bytes:
    """What the store keeps for a work, for whoever prepares it elsewhere (the PDF reader, 2026-11-04)."""
    source = extract_musicxml(content)
    if source is None:
        raise NotMusicXML('La partitura no es MusicXML válido.')
    return _encode(_read_timeline(source))


def timeline_has_parts(data: bytes) -> bool:
    """Whether what came from elsewhere can be cut into passages."""
    try:
        return bool(_decode(data).parts)
    except Exception:
        return False


# Each note of a trill, mordent or turn lasts about this long, as played (music21 writes 32nds at any tempo: at ♩=50 a
# trill crawled); the nearest of these lengths keeps the trill filling its note.
ORNAMENT_SECONDS = 0.07
ORNAMENT_QUARTERS = (0.125, 0.0625, 0.03125)


def _ornament_notes(event, bpm: float) -> Optional[list]:
    """(start from the note, length, MIDI) of the notes a trill, mordent or turn stands for, in the key of the work and
    at the speed of its tempo; None for a note without one, or one music21 cannot realise (it then sounds as written)."""
    if type(event) is not note.Note:
        return None
    ornament = next((item for item in event.expressions if isinstance(item, expressions.Ornament)
                     and hasattr(item, 'realize')), None)
    if ornament is None:
        return None
    wanted = ORNAMENT_SECONDS * bpm / 60
    ornament.quarterLength = min(ORNAMENT_QUARTERS, key=lambda length: abs(math.log2(length / wanted)))
    try:
        before, main, after = ornament.realize(event)
    except Exception:
        return None
    found, at = [], 0.0
    for item in [*before, *([main] if main is not None else []), *after]:
        length = float(item.duration.quarterLength)
        if length <= 0:
            continue
        found.append((at, length, float(item.pitch.midi)))
        at += length
    return found or None


class _BandMeasures:
    """Where each measure starts for the whole band (2026-11-20). A part read from a PDF can have a measure a beat too
    long or too short; timed on its own measures, it then sounded late or early until the end. Each measure lasts what
    most parts give it (on a tie, its time signature, else the longest); a part's notes keep their place inside the
    measure, a beat it has too many is left out and a missing one is a rest."""

    def __init__(self, parts):
        self.own = []   # where each part's measures start as written
        lengths_by_index = []
        for part in parts:
            measures = list(part.getElementsByClass(stream.Measure))
            starts = [float(m.offset) for m in measures]
            lengths = [float(m.duration.quarterLength) for m in measures]
            self.own.append(starts)
            for index, measure in enumerate(measures):
                if index == len(lengths_by_index):
                    lengths_by_index.append((Counter(), float(measure.barDuration.quarterLength)))
                lengths_by_index[index][0][lengths[index]] += 1
        self.lengths, self.starts, at = [], [], 0.0
        for votes, written in lengths_by_index:
            most = max(votes.values())
            tied = [length for length, count in votes.items() if count == most]
            length = written if written in tied else max(tied)
            self.starts.append(at)
            self.lengths.append(length)
            at += length
        self.end = at

    def onset(self, part: int, offset: float) -> Optional[float]:
        """The band's time of a note starting there in the part; None for a beat the measure has too many."""
        starts = self.own[part]
        if not starts:
            return offset
        index = max(0, bisect_right(starts, offset) - 1)
        inside = offset - starts[index]
        return self.starts[index] + inside if inside < self.lengths[index] else None

    def release(self, part: int, offset: float) -> float:
        """The band's time of a note ending there in the part, cut at the end of its measure."""
        starts = self.own[part]
        if not starts:
            return offset
        index = max(0, bisect_left(starts, offset) - 1)
        return self.starts[index] + min(offset - starts[index], self.lengths[index])

    def measures(self, numbers) -> tuple:
        """(number, band start) of a part's measures."""
        return tuple((number, self.starts[index]) for index, number in enumerate(numbers))


def _read_timeline(content: bytes) -> _Timeline:
    # From the bytes, as the analysis parser: music21 then does not write its own cache to disk.
    score = converter.parse(content, format='musicxml')
    declared = read_part_metadata(content)
    changes = note_instruments(content)
    raw_names = [part.partName or (part.id if isinstance(part.id, str) else f'Part {i}')
                 for i, part in enumerate(score.parts, 1)]
    band = _BandMeasures(score.parts)
    marks = {}
    for index, part in enumerate(score.parts):
        for mark in part.recurse().getElementsByClass(tempo.MetronomeMark):
            at = band.onset(index, float(mark.getOffsetInHierarchy(part)))
            if mark.number is not None and mark.getQuarterBPM() > 0 and at is not None:
                marks.setdefault(at, float(mark.getQuarterBPM()))
    mark_offsets = sorted(marks)

    def bpm_at(offset: float) -> float:
        at = bisect_right(mark_offsets, offset) - 1
        return marks[mark_offsets[at]] if at >= 0 else 120.0

    counts, indexes = Counter(raw_names), Counter()
    parts, total = [], 0
    for part_index, (part, name) in enumerate(zip(score.parts, raw_names)):
        if counts[name] > 1:
            indexes[name] += 1
            staff = re.search(r'-Staff(\d+)$', str(part.id))
            name = f'{name} {int(staff.group(1)) if staff else indexes[name]}'
        # Everything read from the written part comes first: the score is then changed in place, which
        # saves the deep copies that took two thirds of the time (nobody else uses this parsed score).
        identity = _identity(part, name, declared)
        program = part.getInstrument().midiProgram
        # A first measure numbered 0 is an upbeat (2026-11-22); 0 elsewhere is music21's measure without a number.
        written_measures = [(int(m.number if m.number or i == 1 else i), float(m.offset))
                            for i, m in enumerate(part.getElementsByClass(stream.Measure), 1)]
        measures = band.measures([number for number, _ in written_measures])
        highest_time = band.end
        metadata = metadata_for_part(part, declared)
        change = changes.get(metadata.part_id)
        instruments = change[0] if change else (None,)
        starts = [offset for _, offset in written_measures]

        def played(event) -> Optional[str]:
            """The instrument of a note of a part that changes instrument (2026-11-17), by where the written note stands."""
            if change is None:
                return None
            at = max(0, bisect_right(starts, float(event.offset)) - 1)
            return change[1].get(note_key(metadata.staff_number, at, float(event.offset) - starts[at]) if starts else None,
                                 instruments[0])

        written = {id(event): played(event) for event in part.flatten().notes}
        part.toSoundingPitch(inPlace=True)
        part.stripTies(inPlace=True)
        by_instrument = {instrument: [] for instrument in instruments}
        identities = {instrument: identity if instrument is None else _changed_identity(instrument, identity)
                      for instrument in instruments}
        events = list(part.flatten().notes)
        for index, event in enumerate(events):
            instrument = written.get(id(event), instruments[0])
            notes, identity = by_instrument[instrument], identities[instrument]
            onset = band.onset(part_index, float(event.offset))
            if onset is None:
                continue
            release = band.release(part_index, float(event.offset) + float(event.duration.quarterLength))
            if event.duration.isGrace:
                following = 0
                while index + following + 1 < len(events) and events[index + following + 1].duration.isGrace:
                    following += 1
                onset = max(0.0, onset - (following + 1) * GRACE_QUARTERS)
                release = onset + GRACE_QUARTERS
            # Simultaneous drum-set hits arrive as a PercussionChord, not as chord.Chord.
            hits = (list(event.notes) if isinstance(event, m21_percussion.PercussionChord)
                    else [event] if isinstance(event, note.Unpitched) else [])
            if hits:
                notes.append(_Note(onset, release, drums=tuple(_drum_note(hit, part, name) for hit in hits)))
            elif not event.duration.isGrace and (ornamented := _ornament_notes(event, bpm_at(onset))):
                notes.extend(_Note(onset + start, onset + start + length, pitches=(midi,)) for start, length, midi in ornamented)
            else:
                pitches = event.pitches if isinstance(event, chord.Chord) else (event.pitch,)
                drums = tuple(key for key in (_unpitched_key(identity, pitch.midi) for pitch in pitches) if key is not None)
                notes.append(_Note(onset, release, drums=drums) if drums
                             else _Note(onset, release, pitches=tuple(float(pitch.midi) for pitch in pitches)))
        total += len(events)
        if total > MAX_PREPARED_NOTES:
            raise ValueError('La partitura es demasiado larga para reproducirla.')
        for instrument, notes in by_instrument.items():
            identity = identities[instrument]
            parts.append(_Part(name if instrument is None else split_name(name, instrument), program,
                               identity.canonical_id if identity else None, identity.sound if identity else None, measures,
                               highest_time, tuple(notes)))
    return _Timeline(tuple(parts), marks, band.end)


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
