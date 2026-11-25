"""Clefs the PDF reader mistakes on some pages (2026-11-25, «1812»): trumpets and horns in bass clef, trombones in treble
clef, so every note of the page sounded a sixth away. The band tells: with the right clef its parts double the notes."""
from xml.etree import ElementTree as ET

from backend.parsers.pdf_clefs import fix_clefs

LINE = {"G": 2, "F": 4}


def note(pitch, duration=1, accidental=None):
    if pitch is None:
        return f"<note><rest/><duration>{duration}</duration></note>"
    alter = {"#": "<alter>1</alter>", "b": "<alter>-1</alter>"}.get(pitch[1], "")
    return (f"<note><pitch><step>{pitch[0]}</step>{alter}<octave>{pitch[-1]}</octave></pitch><duration>{duration}</duration>"
            + (f"<accidental>{accidental}</accidental>" if accidental else "") + "</note>")


def notes(*names):
    return "".join(note(name) for name in names)


def clef(sign):
    return f"<clef><sign>{sign}</sign><line>{LINE[sign]}</line></clef>"


def work(*parts):
    """(name, fifths, [(clef or None, measure)]) per part."""
    names = "".join(f'<score-part id="P{at}"><part-name>{name}</part-name></score-part>' for at, (name, *_rest) in enumerate(parts))
    body = ""
    for at, (_name, fifths, measures) in enumerate(parts):
        body += f'<part id="P{at}">'
        for number, (sign, measure) in enumerate(measures, 1):
            inside = ("<divisions>1</divisions>" f"<key><fifths>{fifths}</fifths></key>" if number == 1 else "") + (clef(sign) if sign else "")
            body += f'<measure number="{number}">' + (f"<attributes>{inside}</attributes>" if inside else "") + measure + "</measure>"
        body += "</part>"
    return f"<score-partwise><part-list>{names}</part-list>{body}</score-partwise>".encode()


def read(musicxml, part=0, measure=0):
    found = ET.fromstring(musicxml).findall("part")[part].findall("measure")[measure]
    sign = {"1": "#", "-1": "b", None: ""}
    return [item.findtext("pitch/step") + sign[item.findtext("pitch/alter")] + item.findtext("pitch/octave")
            for item in found.findall("note") if item.find("pitch") is not None]


def clefs(musicxml, part=0):
    return [(m.get("number"), m.findtext("attributes/clef/sign"), m.findtext("attributes/clef/line"))
            for m in ET.fromstring(musicxml).findall("part")[part].findall("measure") if m.find("attributes/clef") is not None]


# Eight notes sounding C D E F G A B C in four instruments that sound as written.
SCALE = ("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5")
LOW = tuple(name[0] + str(int(name[1]) - 1) for name in SCALE)
BAND = [("Flute", 0, [("G", notes(*SCALE))] * 1 + [(None, notes(*SCALE))]), ("Oboe", 0, [("G", notes(*SCALE)), (None, notes(*SCALE))]),
        ("Bassoon", 0, [("F", notes(*LOW)), (None, notes(*LOW))]), ("Tuba", 0, [("F", notes(*LOW)), (None, notes(*LOW))])]
# The same places of the staff, read in the other clef: a treble C4 is a bass E2, twelve steps below.
TREBLE_AS_BASS = ("E2", "F2", "G2", "A2", "B2", "C3", "D3", "E3")
BASS_AS_TREBLE = ("A4", "B4", "C5", "D5", "E5", "F5", "G5", "A5")


def test_a_trumpet_in_c_read_in_bass_clef_goes_back_to_treble():
    content = work(("Trumpet in C", 0, [("G", notes(*SCALE)), ("F", notes(*TREBLE_AS_BASS))]), *BAND)
    fixed, parts = fix_clefs(content)
    assert read(fixed, measure=1) == list(SCALE)
    assert clefs(fixed) == [("1", "G", "2"), ("2", "G", "2")]
    assert parts == {"P0"}


def test_a_transposing_part_is_judged_at_its_sounding_pitch():
    written = ("D4", "E4", "F#4", "G4", "A4", "B4", "C#5", "D5")       # B♭ trumpet, key of D
    in_bass = ("F2", "G2", "A2", "B2", "C3", "D3", "E3", "F3")
    content = work(("Trumpet in Bb 4", 2, [("G", notes(*written)), ("F", "".join(
        note(name[0] + ("#" if name[0] in "FC" else "") + name[-1]) for name in in_bass))]), *BAND)
    fixed, _ = fix_clefs(content)
    assert read(fixed, measure=1) == list(written), "the notes of the key are the key's in the new place"


def test_a_printed_accidental_stays_with_its_note_until_the_bar_line():
    content = work(("Trumpet in C", 0, [("F", note("E2") + note("A2", accidental="sharp") + note("A#2") + notes(*TREBLE_AS_BASS[:5])), (None, notes(*TREBLE_AS_BASS))]), *BAND)
    content = content.replace(b"<step>A</step><octave>2</octave></pitch><duration>1</duration><accidental>", b"<step>A</step><alter>1</alter><octave>2</octave></pitch><duration>1</duration><accidental>")
    fixed, _ = fix_clefs(content)
    assert read(fixed)[:3] == ["C4", "F#4", "F#4"]


def test_a_trombone_takes_the_clef_the_band_proves_on_each_page():
    content = work(("Trombone 1", 0, [("G", notes(*BASS_AS_TREBLE)), ("F", notes(*LOW))]), *BAND)
    fixed, _ = fix_clefs(content)
    assert read(fixed, measure=0) == list(LOW)
    assert read(fixed, measure=1) == list(LOW)
    assert clefs(fixed)[0] == ("1", "F", "4")


def test_a_page_with_too_few_notes_takes_the_clef_of_the_rest_of_its_part():
    content = work(("Trombone 1", 0, [("G", note("A4", 8)), ("F", notes(*LOW))]), *BAND)
    fixed, _ = fix_clefs(content)
    assert read(fixed) == ["C3"] and clefs(fixed)[0] == ("1", "F", "4")


def test_a_trombone_always_in_treble_clef_is_left_alone():
    content = work(("Trombone 1", 2, [("G", notes("D4", "E4", "F#4", "G4", "A4", "B4", "C#5", "D5"))] * 1), *BAND)
    assert fix_clefs(content) == (content, frozenset())


def test_a_real_change_of_clef_is_kept():
    # A bassoon or a euphonium may be written in both: the band doubles both as they were read.
    content = work(("Euphonium", 0, [("F", notes(*LOW)), ("F", notes(*LOW))]), *BAND)
    assert fix_clefs(content) == (content, frozenset())
    # B♭ treble clef, sounding the band's notes a ninth below.
    content = work(("Euphonium", 0, [("F", notes(*LOW)), ("G", "".join(note(n) for n in ("D4", "E4", "F#4", "G4", "A4", "B4", "C#5", "D5")))]), *BAND)
    assert fix_clefs(content) == (content, frozenset())


def test_parts_misread_together_do_not_prove_each_other():
    # «1812» bar 88: five low parts read in treble clef agreed among themselves.
    wrong = [(name, 0, [("G", notes(*BASS_AS_TREBLE)), ("F", notes(*LOW))]) for name in ("Trombone 1", "Trombone 2", "Trombone 3", "Tuba 2", "Double Bass")]
    fixed, parts = fix_clefs(work(*wrong, *BAND))
    assert all(read(fixed, part=at) == list(LOW) for at in range(5)) and len(parts) == 5


def test_a_staff_that_is_not_the_trumpet_s_is_left_as_read():
    # In bass clef it doubles the band: another instrument's staff taken for the trumpet's, not a wrong clef.
    content = work(("Trumpet in C", 0, [("G", notes(*SCALE)), ("F", notes(*LOW))]), *BAND)
    assert fix_clefs(content)[0] == content


def test_percussion_unknown_parts_and_other_clefs_are_left_alone():
    content = work(("Parte 9", 0, [("G", notes(*SCALE)), ("F", notes(*TREBLE_AS_BASS))]),
                   ("Timpani", 0, [("G", notes(*SCALE)), ("F", notes(*TREBLE_AS_BASS))]), *BAND)
    assert fix_clefs(content) == (content, frozenset())


def test_the_work_is_prepared_with_the_clefs_and_the_key_of_the_band():
    from backend.parsers.prepare import final_musicxml
    flats = lambda names: tuple(n[0] + ("b" if n[0] in "BEA" else "") + n[-1] for n in names)
    band = [(name, -3, [(sign, notes(*flats(scale))), (None, notes(*flats(scale)))]) for name, sign, scale in
            (("Flute", "G", SCALE), ("Oboe", "G", SCALE), ("Bassoon", "F", LOW), ("Tuba", "F", LOW))]
    # Read in treble clef and with two flats instead of three (A natural).
    wrong = tuple(n[0] + ("b" if n[0] in "BE" else "") + n[-1] for n in BASS_AS_TREBLE)
    content = work(("Trombone 1", -2, [("G", notes(*wrong)), ("F", notes(*flats(LOW)))]), *band)
    final = final_musicxml(content.replace(b"</key>", b"</key><time><beats>8</beats><beat-type>4</beat-type></time>"), None, False, "score")
    assert read(final) == list(flats(LOW))
    assert b"<transpose>" not in final
