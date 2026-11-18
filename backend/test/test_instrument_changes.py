"""A part that changes instrument (2026-11-17): «Mallet Percussion» of «Pirates of the Caribbean» plays tambourine, bells,
chimes and gong; the xylophone of «Oregon Trail II» goes «To Wood Blocks». Each instrument becomes a part of its own, with
rests where the other plays, so that its range, difficulty and sound are its own; one player still plays them all."""
from pathlib import Path

import pytest

from backend.analyzers.band_fit import compute_band_fit
from backend.domain.instrument_resolver import resolve_part
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.playback import build_playback, clear_timelines

HEADER = '<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>'
ATTRIBUTES = "<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>"


def note(step, octave, instrument=None):
    named = f'<instrument id="{instrument}"/>' if instrument else ""
    return f"<note><pitch><step>{step}</step><octave>{octave}</octave></pitch><duration>1</duration>{named}<type>quarter</type></note>"


def drum(step, octave, instrument):
    return (f'<note><unpitched><display-step>{step}</display-step><display-octave>{octave}</display-octave></unpitched>'
            f'<duration>1</duration><instrument id="{instrument}"/><type>quarter</type></note>')


def score_part(part_id, name, *instruments):
    declared = "".join(f'<score-instrument id="{part_id}-I{number}"><instrument-name>{instrument}</instrument-name></score-instrument>'
                       for number, instrument in enumerate(instruments, 1))
    return f'<score-part id="{part_id}"><part-name>{name}</part-name>{declared}</score-part>'


XYLOPHONE = ('<part id="P1"><measure number="1">' + ATTRIBUTES + note("C", 5, "P1-I1") * 4 + "</measure>"
             '<measure number="2"><direction><direction-type><words>To Wood Blocks</words></direction-type></direction>'
             + note("F", 4, "P1-I2") * 4 + "</measure></part>")
DRUMS = ('<part id="P2"><measure number="1">' + ATTRIBUTES.replace("<sign>G</sign><line>2</line>", "<sign>percussion</sign>")
         + drum("C", 5, "P2-I1") * 2 + drum("F", 4, "P2-I2") * 2 + '</measure><measure number="2">'
         + drum("C", 5, "P2-I1") * 4 + "</measure></part>")
# No instrument on its notes: <sound><instrument-change> says which plays from there on.
MALLETS = ('<part id="P3"><measure number="1">' + ATTRIBUTES + note("A", 5) * 4 + "</measure>"
           '<measure number="2"><direction><direction-type><words>Tambourine</words></direction-type>'
           '<sound><instrument-change id="P3-I2"/></sound></direction>' + note("B", 4) * 4 + "</measure></part>")
SCORE = (HEADER + score_part("P1", "Xylophone", "Xylophone", "Wood Blocks") + score_part("P2", "Drumset", "Acoustic Snare", "Bass Drum")
         + score_part("P3", "Mallet Percussion", "Bells", "Tambourine") + "</part-list>" + XYLOPHONE + DRUMS + MALLETS
         + "</score-partwise>")


@pytest.fixture
def changes(tmp_path) -> Path:
    path = tmp_path / "changes.musicxml"
    path.write_text(SCORE)
    return path


def pitches(part, number):
    return [item.pitch for item in part.measures[number - 1].notes if not item.is_rest]


def test_each_instrument_of_a_part_is_a_part_of_its_own(changes):
    parts = {part.name: part for part in parse_musicxml(changes).parts}
    assert list(parts) == ["Xylophone", "Xylophone (Wood Blocks)", "Drumset", "Mallet Percussion (Bells)",
                           "Mallet Percussion (Tambourine)"], "a drum set stays one part"
    assert pitches(parts["Xylophone"], 1) == ["C5"] * 4 and pitches(parts["Xylophone"], 2) == []
    assert pitches(parts["Xylophone (Wood Blocks)"], 1) == [] and pitches(parts["Xylophone (Wood Blocks)"], 2) == ["F4"] * 4
    assert pitches(parts["Mallet Percussion (Bells)"], 1) == ["A5"] * 4
    assert pitches(parts["Mallet Percussion (Tambourine)"], 2) == ["B4"] * 4
    rests = parts["Xylophone"].measures[1]
    assert sum(item.duration_quarters for item in rests.notes) == 4, "the other instrument's notes become rests"


def test_each_part_is_its_instrument(changes):
    parts = {part.name: part for part in parse_musicxml(changes).parts}
    assert resolve_part(parts["Xylophone"]).identity.canonical_id == "xylophone"
    assert resolve_part(parts["Mallet Percussion (Bells)"]).identity.canonical_id == "glockenspiel"
    assert resolve_part(parts["Mallet Percussion (Tambourine)"]).identity.canonical_id == "tambourine"


def test_one_player_still_plays_all_the_instruments_of_a_part(changes):
    score = parse_musicxml(changes)
    split, whole = score.parts[3:5], score.parts[3:4]
    percussion = lambda parts: next(item for item in compute_band_fit(type(score)(score.title, tuple(parts)), {})["requirements"]
                                    if item["key"] == "percussion")["required"]
    assert percussion(split) == percussion(whole) == 1


def test_each_instrument_sounds_as_itself(changes):
    clear_timelines()
    tracks = {track["instrument"]: track for track in build_playback(changes, "", 1, 2)["tracks"]}
    assert set(tracks) == {"Xylophone", "Xylophone (Wood Blocks)", "Drumset", "Mallet Percussion (Bells)",
                           "Mallet Percussion (Tambourine)"}
    assert len(tracks["Mallet Percussion (Bells)"]["events"]) == 4 and not tracks["Mallet Percussion (Bells)"].get("percussion")
    assert not tracks["Mallet Percussion (Tambourine)"]["events"] and len(tracks["Mallet Percussion (Tambourine)"]["percussion"]) == 4
    assert len(tracks["Xylophone"]["events"]) == 4
