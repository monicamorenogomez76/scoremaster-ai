"""The parsed musical model of a work as gzipped JSON, kept so that proposals do not read the MusicXML
again (2026-10-07: proposing a concert plan with Persis took minutes on Render's free plan)."""
from dataclasses import asdict
import gzip
import json
import zlib

from backend.domain.models import (PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart,
                                   TempoMark)

# Stored scores of another version are parsed again.
SCORE_VERSION = 'score-v1'


def encode_score(score: Score) -> bytes:
    return gzip.compress(json.dumps(asdict(score)).encode())


def _note(raw: dict) -> ScoreNote:
    return ScoreNote(**{**raw, 'chord_pitches': tuple(raw['chord_pitches'])})


def _metadata(raw: dict) -> PartMetadata:
    transposition = raw['transposition']
    return PartMetadata(**{**raw, **{key: tuple(raw[key]) for key in
                                     ('instrument_names', 'instrument_sounds', 'midi_programs', 'midi_channels')},
                           'transposition': PartTransposition(**transposition) if transposition else None})


def decode_score(data: bytes) -> Score:
    try:
        raw = json.loads(gzip.decompress(data))
        return Score(raw['title'],
                     tuple(ScorePart(part['name'],
                                     tuple(ScoreMeasure(measure['number'], tuple(_note(note) for note in measure['notes']),
                                                        measure['duration_quarters'])
                                           for measure in part['measures']),
                                     _metadata(part['metadata']))
                           for part in raw['parts']),
                     tuple(TempoMark(**mark) for mark in raw['tempo_marks']),
                     raw['composer'])
    except (OSError, EOFError, zlib.error, ValueError, KeyError, TypeError) as exc:
        raise ValueError('No es un modelo de partitura guardado.') from exc
