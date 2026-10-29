"""A key signature copista missed is taken from the band (2026-10-29). In «Paco el barba» six B♭ parts read their first
page with no key signature, two sharps from the second: the notes without an accidental of their own sounded F and C
where the page has F♯ and C♯. The non-transposing parts give the work's key; each transposed part must have that key
plus its instrument's interval. The accidentals printed on the page were read well and stay."""
from music21 import converter

from backend.parsers.pdf_transpositions import add_transpositions, fix_key_signatures


def note(step, alter=0, accidental=None, octave=5, tie=None):
    return (f"<note><pitch><step>{step}</step>{f'<alter>{alter}</alter>' if alter else ''}<octave>{octave}</octave>"
            f"</pitch><duration>2</duration>{f'<tie type={chr(34)}{tie}{chr(34)}/>' if tie else ''}<type>quarter</type>"
            f"{f'<accidental>{accidental}</accidental>' if accidental else ''}</note>")


def part(fifths_by_measure: dict, measures: list[str], clef="G") -> str:
    """fifths_by_measure: the key read at the measures where it changes; each measure is 2/4 at 2 divisions."""
    body = ""
    for number, content in enumerate(measures, 1):
        attributes = ""
        if number in fifths_by_measure or number == 1:
            key = f"<key><fifths>{fifths_by_measure.get(number, 0)}</fifths></key>"
            attributes = ("<attributes>" + ("<divisions>2</divisions>" if number == 1 else "") + key
                          + ("<time><beats>2</beats><beat-type>4</beat-type></time>"
                             f"<clef><sign>{clef}</sign><line>{2 if clef == 'G' else 4}</line></clef>" if number == 1 else "")
                          + "</attributes>")
        body += f'<measure number="{number}">{attributes}{content}</measure>'
    return body


REST = '<note><rest/><duration>4</duration></note>'


def work(*parts: tuple) -> bytes:
    """(part name, keys, measures[, clef]) per part, already transposed as a reading is when it arrives."""
    part_list = "".join(f'<score-part id="P{n}"><part-name>{item[0]}</part-name></score-part>' for n, item in enumerate(parts, 1))
    body = "".join(f'<part id="P{n}">{part(item[1], item[2], *item[3:])}</part>' for n, item in enumerate(parts, 1))
    read = (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>{part_list}</part-list>'
            f'{body}</score-partwise>').encode()
    return add_transpositions(read)


def written(musicxml: bytes, index: int) -> list[str]:
    score = converter.parseData(musicxml.decode(), format="musicxml")
    return [n.pitch.name for n in score.parts[index].flatten().notes]


def keys(musicxml: bytes, index: int) -> list[int]:
    score = converter.parseData(musicxml.decode(), format="musicxml")
    return [k.sharps for k in score.parts[index].flatten().getElementsByClass("KeySignature")]


BAND = (("Flute", {}, [REST] * 3), ("Trombone 1", {}, [REST] * 3, "F"), ("Tuba", {}, [REST] * 3, "F"))


def test_a_b_flat_part_that_missed_its_first_key_signature_takes_two_sharps():
    clarinet = ("Clarinet in B b 1", {1: 0, 3: 2},
                [note("F") + note("C"), note("F", accidental="natural") + note("F"), note("F", 1) + note("C", 1)])
    fixed = fix_key_signatures(work(*BAND, clarinet))
    assert keys(fixed, 3) == [2]
    assert written(fixed, 3) == ["F#", "C#", "F", "F", "F#", "C#"], \
        "the natural printed on the page stays, and lasts until the bar line"


def test_a_part_with_its_key_right_and_a_band_that_changes_key_together_are_left_as_they_are():
    trumpet = ("Trumpet in B b 2", {1: 2, 3: 3}, [note("F", 1), note("F", 1), note("G", 1)])
    band = tuple((name, {3: 1}, measures, *clef) for name, _, measures, *clef in BAND)
    read = work(*band, trumpet)
    assert fix_key_signatures(read) == read


def test_a_horn_and_an_alto_saxophone_take_their_own_interval():
    horn = ("Horn in F 1", {1: 0}, [note("F"), REST, REST])
    alto = ("Alto Sax. 1", {1: 0}, [note("F") + note("C"), REST, REST])
    fixed = fix_key_signatures(work(*BAND, horn, alto))
    assert (keys(fixed, 3), keys(fixed, 4)) == ([1], [3])
    assert (written(fixed, 3), written(fixed, 4)) == (["F#"], ["F#", "C#"])


def test_a_tied_note_keeps_the_pitch_it_continues():
    clarinet = ("Clarinet in B b 1", {1: 0, 2: 2}, [note("C", tie="start"), note("C", tie="stop"), REST])
    assert written(fix_key_signatures(work(*BAND, clarinet)), 3) == ["C#", "C#"]


def test_without_a_band_to_compare_nothing_is_changed():
    alone = work(("Clarinet in B b 1", {1: 0, 2: 2}, [note("F"), note("F"), REST]), ("Tuba", {}, [REST] * 3, "F"))
    assert fix_key_signatures(alone) == alone, "one part alone does not say the work's key"


def test_a_score_in_c_without_transpositions_is_left_as_it_is():
    read = (b'<?xml version="1.0"?><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Clarinet in Bb'
            b'</part-name></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>2</divisions>'
            b'<key><fifths>0</fifths></key></attributes>' + note("F").encode() + b'</measure></part></score-partwise>')
    assert fix_key_signatures(read) == read
