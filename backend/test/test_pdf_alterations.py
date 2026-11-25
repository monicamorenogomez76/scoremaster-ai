"""Alterations the PDF reader hears without a printed accidental (2026-11-25, «1812» bar 20: the second alto saxophone
read G♯ where the page prints G, a semitone from the four instruments that double it)."""
from xml.etree import ElementTree as ET

from backend.parsers.pdf_alterations import fix_unwritten_alterations


def note(pitch, duration=4, accidental=None, tie=None, chord=False):
    """«G4», «G#4» or «Bb4»; None is a rest."""
    if pitch is None:
        return f"<note><rest/><duration>{duration}</duration></note>"
    step, octave = pitch[0], pitch[-1]
    alter = {"#": "<alter>1</alter>", "b": "<alter>-1</alter>"}.get(pitch[1], "")
    return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{step}</step>{alter}<octave>{octave}</octave></pitch><duration>{duration}</duration>"
            + (f'<tie type="{tie}"/>' if tie else "") + (f"<accidental>{accidental}</accidental>" if accidental else "") + "</note>")


def work(*parts):
    """(name, transpose in semitones, fifths, [measures]) per part."""
    names = "".join(f'<score-part id="P{at}"><part-name>{name}</part-name></score-part>' for at, (name, *_rest) in enumerate(parts))
    body = ""
    for at, (_name, semitones, fifths, measures) in enumerate(parts):
        transpose = f"<transpose><chromatic>{semitones}</chromatic></transpose>" if semitones else ""
        first = f"<attributes><divisions>1</divisions><key><fifths>{fifths}</fifths></key>{transpose}</attributes>"
        body += f'<part id="P{at}">' + "".join(
            f'<measure number="{number}">{first if number == 1 else ""}{measure}</measure>' for number, measure in enumerate(measures, 1)) + "</part>"
    return f"<score-partwise><part-list>{names}</part-list>{body}</score-partwise>".encode()


def pitches(musicxml, part=0):
    found = ET.fromstring(musicxml).findall("part")[part]
    sign = {"1": "#", "-1": "b", None: ""}
    return [item.findtext("pitch/step") + sign[item.findtext("pitch/alter")] + item.findtext("pitch/octave")
            for item in found.iter("note") if item.find("pitch") is not None]


# B♭ sounding in four instruments: G for an E♭ alto, C for a B♭ bass clarinet.
DOUBLES = [("Tuba", 0, -3, [note("Bb2")]), ("Bass Clarinet in Bb", -2, -1, [note("C4")]), ("Baritone Sax", -9, 0, [note("G4")])]


def alto(*measures):
    return ("Alto Sax 2", -9, 0, list(measures))


def test_a_sharp_nobody_printed_is_taken_out_when_the_band_plays_the_note_without_it():
    assert pitches(fix_unwritten_alterations(work(alto(note("G#4")), *DOUBLES))) == ["G4"]


def test_a_printed_accidental_is_kept_and_lasts_to_the_bar_line():
    for measure in (note("G#4", accidental="sharp"), note("G#4", 2, accidental="sharp") + note("G#4", 2)):
        content = work(alto(measure), *DOUBLES)
        assert fix_unwritten_alterations(content) == content


def test_two_doublings_are_no_proof():
    content = work(alto(note("G#4")), *DOUBLES[:2])
    assert fix_unwritten_alterations(content) == content


def test_one_instrument_playing_the_read_note_keeps_it():
    content = work(alto(note("G#4")), *DOUBLES, ("Flute", 0, -3, [note("B5", accidental="natural")]))
    assert fix_unwritten_alterations(content) == content, "the reader may have missed the sign, not the note"


def test_the_notes_must_start_together():
    # The band holds the natural from before: an unprinted sharp may be a neighbour note whose sign was missed.
    content = work(alto(note("G4", 2) + note("G#4", 2)), *DOUBLES)
    assert fix_unwritten_alterations(content) == content


def test_a_note_of_the_key_read_without_its_flat_takes_it():
    parts = [("Flute 1", 0, -6, [note("C6")])] + [(name, 0, -6, [note("Cb5")]) for name in ("Flute 2", "Oboe", "Bassoon")]
    assert pitches(fix_unwritten_alterations(work(*parts))) == ["Cb6"]


def test_a_tied_note_follows_the_note_it_continues():
    tied = alto(note("G#4", tie="start"), note("G#4", tie="stop"))
    doubles = [(name, semitones, fifths, [measures[0], note(None)]) for name, semitones, fifths, measures in DOUBLES]
    assert pitches(fix_unwritten_alterations(work(tied, *doubles))) == ["G4", "G4"]


def test_a_tie_from_a_printed_accidental_keeps_it():
    tied = alto(note("G#4", accidental="sharp", tie="start"), note("G#4", tie="stop"))
    doubles = [(name, semitones, fifths, [note(None), measures[0]]) for name, semitones, fifths, measures in DOUBLES]
    content = work(tied, *doubles)
    assert fix_unwritten_alterations(content) == content


def test_misread_notes_are_no_proof_of_each_other():
    # Three staves with the same unprinted sharp against one natural: nothing says which is right.
    content = work(alto(note("G#4")), *[("Alto Sax", -9, 0, [note("G#4")])] * 3, DOUBLES[0])
    assert fix_unwritten_alterations(content) == content


def test_percussion_and_unknown_parts_neither_prove_nor_change():
    content = work(alto(note("G#4")), *[(name, 0, -3, [note("Bb4")]) for name in ("Snare Drum", "Parte 7", "Parte 8")])
    assert fix_unwritten_alterations(content) == content
    unknown = work(("Parte 9", -9, 0, [note("G#4")]), *DOUBLES)
    assert fix_unwritten_alterations(unknown) == unknown, "its transposition is not known"


def test_the_work_read_from_a_pdf_is_prepared_without_them():
    from backend.parsers.prepare import final_musicxml
    written = work(("Alto Sax 2", 0, 0, [note("G#4")]), ("Tuba", 0, -3, [note("Bb2")]), ("Bass Clarinet in Bb", 0, -1, [note("C4")]),
                   ("Baritone Sax", 0, 0, [note("G4")]), ("Bassoon", 0, -3, [note("Bb3")]))
    assert pitches(final_musicxml(written, None, False, "parts")) == ["G4"]
