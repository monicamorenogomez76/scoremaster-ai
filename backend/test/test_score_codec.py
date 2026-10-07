"""The musical model of a work is kept as JSON, so proposals do not read the MusicXML again
(2026-10-07: proposing a concert plan with Persis took minutes on Render's free plan)."""
from pathlib import Path

import pytest

from backend.domain.models import (PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart,
                                   TempoMark)
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.score_codec import decode_score, encode_score

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


@pytest.mark.parametrize("name", sorted(path.name for path in SCORES.glob("*.musicxml")))
def test_a_parsed_score_reads_back_the_same(name):
    score = parse_musicxml(SCORES / name)
    assert decode_score(encode_score(score)) == score


def test_every_field_reads_back_the_same():
    note = ScoreNote("C#5", 0.5, offset_quarters=1.5, phrase_mark=True, voice="2", tie="start", is_grace=False,
                     chord_pitches=("A4", "C#5"))
    metadata = PartMetadata("P1", "Clarinet in Bb", "Cl.", ("Clarinet",), ("wind.reed.clarinet.bflat",), (72,), (1,),
                            PartTransposition(-2, -1, 0), 1, "clarinet.bb")
    score = Score("Obra", (ScorePart("Clarinet", (ScoreMeasure(1, (note, ScoreNote(None, 1.0, is_rest=True)), 4.0),),
                                     metadata),),
                  (TempoMark(1, 0.0, 96.0, 1.5),), "Autora")
    again = decode_score(encode_score(score))
    assert again == score
    assert isinstance(again.parts[0].measures[0].notes[0].chord_pitches, tuple)


def test_something_else_is_not_read_as_a_score():
    with pytest.raises(ValueError):
        decode_score(b"not gzip")
