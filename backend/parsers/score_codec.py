"""The parsed musical model of a work as gzipped JSON, kept so that proposals do not read the MusicXML
again (2026-10-07: proposing a concert plan with Persis took minutes on Render's free plan)."""
from dataclasses import asdict
import gzip
import json
import zlib

from backend.domain.models import (PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart,
                                   TempoMark)

# Stored scores of another version are parsed again.
SCORE_VERSION = 'score-v5'   # v5 (2026-11-18): the marks of the structure (barlines, repeats, endings, rehearsal marks, words). v4 (2026-11-17): a part that changes instrument is a part per instrument. v3 (2026-11-05): what coincides on a staff. v2 (2026-10-25): key, meter, tuplets, dynamics, articulation, ornaments


def encode_score(score: Score) -> bytes:
    return gzip.compress(json.dumps(asdict(score)).encode())


def _note(raw: dict) -> ScoreNote:
    return ScoreNote(**{**raw, **{key: tuple(raw[key]) for key in ('chord_pitches', 'articulations', 'ornaments')}})


def _metadata(raw: dict) -> PartMetadata:
    transposition = raw['transposition']
    return PartMetadata(**{**raw, **{key: tuple(raw[key]) for key in
                                     ('instrument_names', 'instrument_sounds', 'midi_programs', 'midi_channels')},
                           'transposition': PartTransposition(**transposition) if transposition else None})


def _measure(raw: dict) -> ScoreMeasure:
    return ScoreMeasure(**{**raw, 'notes': tuple(_note(note) for note in raw['notes']), 'dynamics': tuple(raw['dynamics']),
                           'words': tuple(raw.get('words', ()))})


def decode_score(data: bytes) -> Score:
    try:
        raw = json.loads(gzip.decompress(data))
        return Score(raw['title'],
                     tuple(ScorePart(part['name'],
                                     tuple(_measure(measure) for measure in part['measures']),
                                     _metadata(part['metadata']))
                           for part in raw['parts']),
                     tuple(TempoMark(**mark) for mark in raw['tempo_marks']),
                     raw['composer'])
    except (OSError, EOFError, zlib.error, ValueError, KeyError, TypeError) as exc:
        raise ValueError('No es un modelo de partitura guardado.') from exc
