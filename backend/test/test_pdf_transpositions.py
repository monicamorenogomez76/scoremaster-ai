"""Works read from a PDF sound in the key of each instrument (2026-10-29). copista writes the notes as printed, in the
key of each instrument (a B♭ clarinet's C sounds B♭), but no <transpose>: everything sounded as written, a tone too
high for trumpets and clarinets, a fifth for horns, a sixth for alto saxophones. When a work comes back from the reader,
each part the catalog recognises takes the transposition of its instrument."""
import pytest
from music21 import converter

from backend.domain.instrument_transposition import written_to_sounding
from backend.parsers.pdf_transpositions import add_transpositions
from backend.parsers.musicxml_parser import parse_musicxml


def work(*parts: tuple) -> bytes:
    """A work as the reader sends it: (part name, clef sign[, fifths]) per part, a written C5 in each, no <transpose>."""
    parts = [(part + (0,))[:3] for part in parts]
    part_list = "".join(f'<score-part id="P{n}"><part-name>{name}</part-name></score-part>'
                        for n, (name, _, _) in enumerate(parts, 1))
    body = "".join(
        f'<part id="P{n}"><measure number="1"><attributes><divisions>1</divisions><key><fifths>{fifths}</fifths></key>'
        f'<time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>{sign}</sign><line>{2 if sign == "G" else 4}'
        '</line></clef></attributes><note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration>'
        '<type>whole</type></note></measure></part>' for n, (_, sign, fifths) in enumerate(parts, 1))
    return (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>{part_list}</part-list>'
            f'{body}</score-partwise>').encode()


def sounding(musicxml: bytes) -> list[int]:
    score = converter.parseData(musicxml.decode("utf-8"), format="musicxml").toSoundingPitch()
    return [part.flatten().notes[0].pitch.midi for part in score.parts]


C5 = 72


def test_each_part_sounds_in_the_key_of_its_instrument():
    read = work(("Clarinet in B b 1", "G"), ("Trumpet in Bb 3", "G"), ("Horn in F 1", "G"), ("Alto Sax. 2", "G"),
                ("Tenor Sax.", "G"), ("Baritone Sax.", "G"), ("Clarinet in E b", "G"), ("Bass Clarinet", "G"),
                ("Piccolo", "G"), ("Flute", "G"), ("Oboe", "G"))
    assert sounding(read) == [C5] * 11, "as written before"
    assert sounding(add_transpositions(read)) == [
        C5 - 2, C5 - 2, C5 - 7, C5 - 9, C5 - 14, C5 - 21, C5 + 3, C5 - 14, C5 + 12, C5, C5]


def test_euphonium_and_trombone_in_treble_clef_are_in_b_flat_and_in_bass_clef_as_written():
    read = work(("Euphonium", "G"), ("Euphonium", "F"), ("Trombone 1", "G"), ("Trombone 2", "F"), ("Tuba", "F"))
    assert sounding(add_transpositions(read)) == [C5 - 14, C5, C5 - 14, C5, C5]


def test_unknown_parts_and_parts_that_already_say_their_transposition_are_left_alone():
    read = work(("Parte 1", "G"), ("Gaita de fole", "G"))
    assert add_transpositions(read) == read
    once = add_transpositions(work(("Trumpet in Bb 1", "G")))
    assert add_transpositions(once).count(b"<transpose>") == 1
    assert sounding(add_transpositions(once)) == [C5 - 2]


def test_a_name_the_account_confirmed_before_counts_too():
    read = work(("Fiscornio 1", "G"))
    assert sounding(add_transpositions(read, {"fiscornio": "flugelhorn.bb"})) == [C5 - 2]


def test_scorelint_reads_the_transposition_added(tmp_path):
    path = tmp_path / "obra.musicxml"
    path.write_bytes(add_transpositions(work(("Horn in F 1", "G"))))
    [part] = parse_musicxml(path).parts
    assert (part.metadata.transposition.chromatic, part.metadata.transposition.diatonic) == (-7, -4)


@pytest.mark.parametrize("canonical_id, interval", [
    ("clarinet.bb", (-2, -1, 0)), ("horn.f", (-7, -4, 0)), ("saxophone.baritone", (-9, -5, -1)),
    ("double_bass", (0, 0, -1)), ("glockenspiel", (0, 0, 2)), ("trumpet.c", None), ("flute", None)])
def test_the_interval_of_each_instrument(canonical_id, interval):
    assert written_to_sounding(canonical_id) == interval


# A score may be printed transposed, each staff in the key of its instrument, or in C, at sounding pitch («Score in C»,
# «Guion en Do»; 2026-10-29). The key signatures tell them apart: in a transposed score a B♭ clarinet has two sharps more
# than the flute and a horn one more; in a score in C they all have the same.
def test_a_transposed_score_is_transposed():
    read = work(("Flute", "G", -2), ("Clarinet in Bb 1", "G", 0), ("Horn in F", "G", -1), ("Alto Sax.", "G", 1),
                ("Trombone", "F", -2))
    assert sounding(add_transpositions(read, source="score")) == [C5, C5 - 2, C5 - 7, C5 - 9, C5]


def test_a_transposed_score_without_key_signatures_is_transposed():
    read = work(("Flute", "G"), ("Clarinet in Bb 1", "G"), ("Trombone", "F"))
    assert sounding(add_transpositions(read, source="score")) == [C5, C5 - 2, C5], "same keys alone say nothing"


def test_a_score_in_c_is_left_at_sounding_pitch():
    read = work(("Flute", "G", -2), ("Clarinet in Bb 1", "G", -2), ("Horn in F", "G", -2), ("Alto Sax.", "G", -2),
                ("Trombone", "F", -2))
    assert add_transpositions(read, source="score") == read
    assert sounding(add_transpositions(read))[1] == C5 - 2, "parts are always in the key of their instrument"
    in_c = work(("Clarinet in Bb 1", "G"), ("Trumpet in Bb", "G"))
    assert add_transpositions(in_c, concert_pitch=True) == in_c, "the reader read «Score in C» on the page"
