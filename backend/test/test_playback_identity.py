"""Playback timbre follows the resolved instrument identity."""
from backend.domain.instrument_catalog import catalog_entries
from backend.parsers.playback import build_playback

PITCHED = "<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><type>whole</type></note>"
UNPITCHED = "<note><unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched><duration>4</duration><type>whole</type></note>"


def score_part(part_id, name, instrument=None):
    declared = "<score-instrument id=\"{0}-I1\"><instrument-name>{1}</instrument-name></score-instrument>".format(part_id, instrument) if instrument else ""
    return "<score-part id=\"{}\"><part-name>{}</part-name>{}</score-part>".format(part_id, name, declared)


def part(part_id, content):
    return '<part id="{}"><measure number="1"><attributes><divisions>1</divisions></attributes>{}</measure></part>'.format(part_id, content)


def write(tmp_path):
    path = tmp_path / "timbres.musicxml"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>'
                    + score_part("P1", "Trompa") + score_part("P2", "Voice", "Clarinet")
                    + score_part("P3", "Voice", "Voice Oohs") + score_part("P4", "Caja")
                    + "</part-list>" + part("P1", PITCHED) + part("P2", PITCHED) + part("P3", PITCHED)
                    + part("P4", UNPITCHED) + "</score-partwise>", encoding="utf-8")
    return path


def test_tracks_carry_identity_and_sound(tmp_path):
    tracks = {track["instrument"]: track for track in build_playback(write(tmp_path), "", 0, 999999)["tracks"]}

    assert (tracks["Trompa"]["canonical_id"], tracks["Trompa"]["sound"]) == ("horn.f", "french_horn")
    assert (tracks["Voice 1"]["canonical_id"], tracks["Voice 1"]["sound"]) == ("clarinet.bb", "clarinet")
    assert (tracks["Voice 2"]["canonical_id"], tracks["Voice 2"]["sound"]) == (None, None)
    assert (tracks["Caja"]["canonical_id"], tracks["Caja"]["sound"]) == ("snare_drum", None)


def test_solo_passage_carries_identity_too(tmp_path):
    solo = build_playback(write(tmp_path), "Trompa", 1, 1)

    assert solo["sound"] == "french_horn"


def test_every_pitched_catalog_identity_has_a_sound():
    unpitched = {"snare_drum", "bass_drum", "crash_cymbals", "suspended_cymbal", "drum_set", "tambourine", "triangle"}
    for entry in catalog_entries():
        assert (entry.sound is None) == (entry.canonical_id in unpitched), entry.canonical_id
