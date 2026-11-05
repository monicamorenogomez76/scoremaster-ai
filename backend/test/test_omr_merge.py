"""PDF scores (decided 2026-10-27): the reader in GitHub Actions (omr/) writes one MusicXML per
page; omr/merge.py joins the pages of a score staff by staff, and the parts read from several PDFs into one work."""
from xml.etree import ElementTree as ET

from backend.parsers.musicxml_parser import parse_musicxml
from omr.merge import combine_parts, join_pages, staff_of


def page(parts: int, measures: int, first_pitch: str = "C") -> bytes:
    """A page as copista writes it: parts Part 1..n, measures numbered from 1, divisions in the first measure."""
    part_list = "".join(f'<score-part id="P{n}"><part-name>Part {n}</part-name></score-part>' for n in range(1, parts + 1))
    body = ""
    for n in range(1, parts + 1):
        bars = ""
        for number in range(1, measures + 1):
            attributes = ("<attributes><divisions>2</divisions><key><fifths>0</fifths></key><time><beats>2</beats>"
                          "<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>"
                          if number == 1 else "")
            bars += (f'<measure number="{number}">{attributes}<note><pitch><step>{first_pitch}</step><octave>5</octave>'
                     "</pitch><duration>4</duration><type>half</type></note></measure>")
        body += f'<part id="P{n}">{bars}</part>'
    return (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>{part_list}</part-list>'
            f"{body}</score-partwise>").encode()


def parts_of(xml: bytes):
    root = ET.fromstring(xml)
    names = [item.findtext("part-name") for item in root.find("part-list").findall("score-part")]
    return root, names, [part.findall("measure") for part in root.findall("part")]


def test_the_pages_of_a_score_are_joined_part_by_part():
    root, names, measures = parts_of(join_pages([page(2, 2, "C"), page(2, 3, "D")], title="Oregon Trail II"))
    assert names == ["Parte 1", "Parte 2"], "without OCR the director confirms the instruments later"
    assert [len(bars) for bars in measures] == [5, 5]
    assert [bar.get("number") for bar in measures[0]] == ["1", "2", "3", "4", "5"]
    assert measures[1][2].find("note/pitch/step").text == "D", "the second page follows the first"
    assert root.findtext("work/work-title") == "Oregon Trail II"


def test_a_part_missing_from_a_page_rests_there_so_the_parts_stay_aligned():
    """A page may show fewer staves (the first page of a score, a section that rests): the part rests for as long."""
    _, names, measures = parts_of(join_pages([page(3, 2), page(2, 2)], title="Obra"))
    assert names == ["Parte 1", "Parte 2", "Parte 3"]
    assert [len(bars) for bars in measures] == [4, 4, 4]
    rest = measures[2][2]
    assert rest.find("note/rest") is not None and rest.find("note/rest").get("measure") == "yes"
    assert rest.findtext("note/type") in (None, "half"), "a whole 2/4 measure"


def test_the_parts_read_from_several_pdfs_are_one_work_named_after_their_files():
    flute, trombone = join_pages([page(1, 2)], title="x"), join_pages([page(1, 3, "E")], title="x")
    _, names, measures = parts_of(combine_parts([("Flauta 1.pdf", flute), ("Trombón 1.pdf", trombone)], title="Obra"))
    assert names == ["Flauta 1", "Trombón 1"]
    assert [len(bars) for bars in measures] == [2, 3]


def test_a_pdf_with_several_parts_numbers_them_after_its_file():
    _, names, _ = parts_of(combine_parts([("Clarinetes.pdf", join_pages([page(2, 1)], title="x"))], title="Obra"))
    assert names == ["Clarinetes 1", "Clarinetes 2"]


def test_staves_grouped_differently_on_each_page_are_aligned_by_clef_and_key():
    """copista groups the staves under a page's braces, and a resting staff may be left out: here the second page
    lacks the middle staff (bass clef), and its last staff (C clef, two sharps) still joins the last part."""
    def staff(number, sign, line, fifths, step):
        return (f'<part id="P{number}"><measure number="1"><attributes><divisions>1</divisions><key><fifths>{fifths}'
                f'</fifths></key><time><beats>2</beats><beat-type>4</beat-type></time><clef><sign>{sign}</sign><line>{line}'
                f'</line></clef></attributes><note><pitch><step>{step}</step><octave>4</octave></pitch><duration>2</duration>'
                '<type>half</type></note></measure></part>')

    def score(*staves):
        names = "".join(f'<score-part id="P{n}"><part-name>Part {n}</part-name></score-part>' for n in range(1, len(staves) + 1))
        return f'<score-partwise version="4.0"><part-list>{names}</part-list>{"".join(staves)}</score-partwise>'.encode()

    first = score(staff(1, "G", 2, 0, "C"), staff(2, "F", 4, -1, "D"), staff(3, "C", 3, 2, "E"))
    second = score(staff(1, "G", 2, 0, "F"), staff(2, "C", 3, 2, "G"))
    _, _, measures = parts_of(join_pages([first, second], title="Obra"))
    assert [bar.findtext("note/pitch/step") for bar in measures[2]] == ["E", "G"], "the C-clef staff stays together"
    assert measures[1][1].find("note/rest") is not None, "the bass staff rests on the second page"


def test_scorelint_reads_the_joined_work(tmp_path):
    path = tmp_path / "obra.musicxml"
    path.write_bytes(join_pages([page(2, 2), page(2, 2)], title="Obra leída"))
    score = parse_musicxml(path)
    assert score.title == "Obra leída"
    assert [len(part.measures) for part in score.parts] == [4, 4]


def test_a_note_too_short_to_write_does_not_spoil_the_work():
    """2026-10-28 («Paco el barba»): copista read an ornament as a 2048th note and music21 refused to write the whole
    work. Notes no music could carry (shorter than a 128th) are dropped; the rest of the measure stays."""
    tiny = page(1, 1).replace(b"<duration>4</duration><type>half</type>",
                              b"<duration>4</duration><type>half</type></note><note><pitch><step>D</step><octave>5</octave>"
                              b"</pitch><duration>1</duration><type>2048th</type><time-modification><actual-notes>3</actual-notes>"
                              b"<normal-notes>2</normal-notes><normal-type>2048th</normal-type></time-modification>")
    root, _, measures = parts_of(join_pages([tiny], title="Obra"))
    assert measures[0][0].findtext("note/pitch/step") == "C"
    assert all(note.findtext("type") != "2048th" for note in measures[0][0].findall("note"))


def work(*staves: list[str]) -> bytes:
    """A work in 2/4: each staff a list of measures, «r» a whole-measure rest, «h» a half note, «q» two quarters."""
    part_list = "".join(f'<score-part id="P{n}"><part-name>Part {n}</part-name></score-part>' for n in range(1, len(staves) + 1))
    notes = {"r": '<note><rest measure="yes"/><duration>4</duration></note>',
             "h": "<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><type>half</type></note>",
             "q": "<note><pitch><step>D</step><octave>5</octave></pitch><duration>2</duration><type>quarter</type></note>" * 2,
             "e": "<note><pitch><step>E</step><octave>5</octave></pitch><duration>1</duration><type>eighth</type></note>" * 4}
    body = ""
    for n, measures in enumerate(staves, 1):
        bars = ""
        for number, content in enumerate(measures, 1):
            attributes = ("<attributes><divisions>2</divisions><key><fifths>0</fifths></key><time><beats>2</beats>"
                          "<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>"
                          if number == 1 else "")
            bars += f'<measure number="{number}">{attributes}{notes[content]}</measure>'
        body += f'<part id="P{n}">{bars}</part>'
    return (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>{part_list}</part-list>'
            f"{body}</score-partwise>").encode()


def contents(xml: bytes) -> list[str]:
    _, _, [measures] = parts_of(xml)
    kinds = []
    for bar in measures:
        found = bar.findall("note")
        kinds.append("r" if all(item.find("rest") is not None for item in found)
                     else {1: "h", 2: "q", 4: "e"}.get(len(found), "?"))
    return kinds


# The score of «Paco el barba» (2026-10-29): copista skips the multi-measure rests of the parts, so each part started a
# different number of measures early. Each part is aligned measure by measure with its score staff.
SCORE = work(list("rrrrqhqhe"), list("hhhhqqqqh"))


def test_a_part_gets_back_the_rests_copista_skipped():
    from omr.merge import fill_lost_rests
    [(name, fixed)] = fill_lost_rests([("Flauta", work(list("rqhqhe")))], SCORE)
    assert name == "Flauta"
    assert contents(fixed) == list("rrrrqhqhe"), "the opening rest of four measures, read as one"


def test_a_rest_lost_in_the_middle_is_put_back_where_it_was():
    from omr.merge import fill_lost_rests
    score = work(list("qhrrrqhe"))
    [(_, fixed)] = fill_lost_rests([("Oboe", work(list("qhrqhe")))], score)
    assert contents(fixed) == list("qhrrrqhe")


def test_a_complete_part_or_one_unlike_every_staff_is_left_as_read():
    from omr.merge import fill_lost_rests
    complete = work(list("hhhhqqqqh"))
    unlike = work(list("eeeeeee"))
    assert fill_lost_rests([("Tuba", complete), ("Otra", unlike)], SCORE) == [("Tuba", complete), ("Otra", unlike)]


def test_a_measure_only_the_part_has_is_kept():
    """Nothing the part read is thrown away: only rests are added."""
    from omr.merge import fill_lost_rests
    [(_, fixed)] = fill_lost_rests([("Flauta", work(list("rqhqhee")))], SCORE)
    assert contents(fixed).count("e") == 2 and contents(fixed)[:4] == list("rrrr")


def test_a_meter_key_or_clef_repeated_in_every_measure_is_written_once():
    """copista writes the time signature again in most measures (2026-11-01, «Paco el barba»): every measure then
    showed its 2/4 and the score viewer could not fit four measures in a line."""
    from omr.merge import combine_parts
    repeated = work(list("hqhq")).replace(b"<note>", b"<attributes><time><beats>2</beats><beat-type>4</beat-type></time>"
                                          b"<clef><sign>G</sign><line>2</line></clef></attributes><note>")
    _, _, [measures] = parts_of(combine_parts([("Flauta", repeated)], "Obra"))
    assert [len(bar.findall("attributes/time")) for bar in measures] == [1, 0, 0, 0]
    assert [len(bar.findall("attributes/clef")) for bar in measures] == [1, 0, 0, 0]


def test_the_work_names_no_composer_it_does_not_know():
    from omr.merge import combine_parts
    assert b"Music21" not in combine_parts([("Flauta", work(list("hq")))], "Obra")


def test_the_parts_aligned_with_the_score_follow_its_order():
    """The parts come in the order of the PDF (2026-11-01: «Paco el barba» put the tuba on top); the score's staves
    give the order of the band."""
    from omr.merge import fill_lost_rests
    files = [("Tuba", work(list("hhhhqqqqh"))), ("Flauta", work(list("rqhqhe")))]
    assert [name for name, _ in fill_lost_rests(files, SCORE)] == ["Flauta", "Tuba"]
    assert [name for name, _ in fill_lost_rests([("Otra", work(list("eeeeeee"))), *files], SCORE)] == \
        ["Flauta", "Tuba", "Otra"], "a part like no staff goes after the others"
    trumpets = [(f"Trompeta {n}", work(list("hhhhqqqqh"))) for n in (3, 2, 1)]
    assert [name for name, _ in fill_lost_rests(trumpets, SCORE)] == ["Trompeta 1", "Trompeta 2", "Trompeta 3"]


def staves_with_clefs(*staves: tuple[list[str], list[str]]) -> bytes:
    """A work whose staves have a clef per measure: «G», «F» or «percussion»."""
    xml = work(*[measures for _, measures in staves]).decode()
    for number, (clefs, _) in enumerate(staves, 1):
        part = xml[xml.index(f'<part id="P{number}">'):]
        part = part[:part.index("</part>")]
        changed = part.replace("<clef><sign>G</sign><line>2</line></clef>", "", 1)
        for index, sign in enumerate(clefs):
            line = {"G": 2, "F": 4}.get(sign)
            clef_xml = f"<clef><sign>{sign}</sign>{f'<line>{line}</line>' if line else ''}</clef>"
            marker = f'<measure number="{index + 1}">'
            at = changed.index(marker) + len(marker)
            changed = changed[:at] + f"<attributes>{clef_xml}</attributes>" + changed[at:] if index else \
                changed.replace("</time></attributes>", "</time>" + clef_xml + "</attributes>", 1)
        xml = xml.replace(part, changed)
    return xml.encode()


# «Arabian Dances» (2026-11-02): the percussion section of its score is printed alone, four systems of timpani and
# percussion 1–4 a page. Joined by clef and key, those five staves went to the first staves with a bass clef (bassoon,
# trombones), because copista reads a percussion clef as a bass clef. The names beside the staves place them.
def test_a_page_with_fewer_staves_is_placed_by_the_names_beside_them():
    from omr.merge import join_pages
    full = staves_with_clefs((["G", "G"], list("hh")), (["F", "F"], list("hh")), (["F", "F"], list("hh")))
    percussion = staves_with_clefs((["F", "F"], list("ee")))
    labels = [["Fl.", "Tuba", "Perc. 1"], ["Perc. 1"]]
    _, _, measures = parts_of(join_pages([full, percussion], "Obra", labels=labels, same=lambda a, b: a == b))
    notes = [[len(bar.findall("note")) if bar.find("note/rest") is None else 0 for bar in staff][2:] for staff in measures]
    assert notes == [[0, 0], [0, 0], [4, 4]], "on the percussion's staff, not on the tuba's"
    _, _, measures = parts_of(join_pages([full, percussion], "Obra"))
    assert [len(bar.findall("note")) for bar in measures[1]][2:] == [4, 4], "without names, by clef as before"


def test_a_percussion_part_is_aligned_only_with_a_percussion_staff():
    from omr.merge import fill_lost_rests
    score = staves_with_clefs((["G"] * 6, list("rrqqqq")), (["F", "F", "percussion", "F", "F", "F"], list("qqqqrr")))
    part = staves_with_clefs((["F", "percussion", "F", "F"], list("qqqq")))
    [(_, fixed)] = fill_lost_rests([("Percussion 1", part)], score)
    assert contents(fixed) == list("qqqqrr"), "its rests where the percussion staff rests, not the flute's"
    flute = staves_with_clefs((["G"] * 4, list("qqqq")))
    [(_, fixed)] = fill_lost_rests([("Flauta", flute)], score)
    assert contents(fixed) == list("rrqqqq"), "and a pitched part never with the percussion staff"
    timpani = staves_with_clefs((["F"] * 4, list("qqqq")))
    assert len(contents(fill_lost_rests([("Timpani", timpani)], score)[0][1])) == 6, "the timpani, with a clef, with either"


def test_a_part_follows_the_staff_of_its_name_before_its_rhythm():
    """Between staves of percussion the rhythms are too alike (2026-11-02: «Percussion 2» and «Percussion 4» of «Arabian
    Dances» swapped staves): the joined score keeps the names beside its staves, and a part with the same name is aligned
    with that staff."""
    from omr.merge import fill_lost_rests, join_pages
    full = staves_with_clefs((["percussion"] * 6, list("qqqqrr")), (["percussion"] * 6, list("rrqqqq")))
    score = join_pages([full], "Obra", labels=[["Perc. 1", "Perc. 2"]], same=lambda a, b: a == b)
    assert parts_of(score)[1] == ["Perc. 1", "Perc. 2"], "the staves keep their names"
    part = staves_with_clefs((["percussion"] * 4, list("qqqq")))
    same = lambda part_name, staff_name: part_name.endswith(staff_name[-1])
    [(_, fixed)] = fill_lost_rests([("Percussion 2", part)], score, same)
    assert contents(fixed) == list("rrqqqq"), "with «Perc. 2», though «Perc. 1» starts with the same rhythm"


def test_a_part_of_its_staff_s_name_is_aligned_even_when_its_rhythm_was_read_unlike():
    from omr.merge import fill_lost_rests, join_pages
    full = staves_with_clefs((["percussion"] * 6, list("eeeerr")), (["percussion"] * 6, list("rrqqqq")))
    score = join_pages([full], "Obra", labels=[["Perc. 1", "Perc. 4"]], same=lambda a, b: a == b)
    part = staves_with_clefs((["percussion"] * 4, list("hhhh")))
    same = lambda part_name, staff_name: part_name[-1] == staff_name[-1]
    [(_, fixed)] = fill_lost_rests([("Percussion 4", part)], score, same)
    assert len(contents(fixed)) == 6, "its staff by name, though no measure of it was read alike"
    [(_, unchanged)] = fill_lost_rests([("Percussion 4", part)], score)
    assert len(contents(unchanged)) == 4, "without names, unlike every staff, it is left as read"


def test_the_staff_of_its_name_wins_over_the_clefs():
    from omr.merge import fill_lost_rests, join_pages
    full = staves_with_clefs((["G"] * 6, list("qqqqrr")), (["percussion"] * 6, list("rrqqqq")))
    score = join_pages([full], "Obra", labels=[["Flauta", "Platos"]], same=lambda a, b: a == b)
    part = staves_with_clefs((["G"] * 4, list("qqqq")))
    [(_, fixed)] = fill_lost_rests([("Platos", part)], score, lambda a, b: a == b)
    assert contents(fixed) == list("rrqqqq"), "the cymbals in treble clef follow their percussion staff"


# --- slurs (2026-11-05): copista writes them, and joining the pages lost every one -------------------------------------

def slurred(first="C", second="D", staves=1) -> bytes:
    """A page with a slur from the first note to the last of a measure, on every staff."""
    bar = ('<attributes><divisions>2</divisions><key><fifths>0</fifths></key><time><beats>2</beats><beat-type>4</beat-type>'
           '</time><clef><sign>G</sign><line>2</line></clef></attributes>'
           f'<note><pitch><step>{first}</step><octave>5</octave></pitch><duration>2</duration><type>quarter</type>'
           '<notations><slur type="start" number="1"/></notations></note>'
           f'<note><pitch><step>{second}</step><octave>5</octave></pitch><duration>2</duration><type>quarter</type>'
           '<notations><slur type="stop" number="1"/></notations></note>')
    names = "".join(f'<score-part id="P{n}"><part-name>Part {n}</part-name></score-part>' for n in range(1, staves + 1))
    body = "".join(f'<part id="P{n}"><measure number="1">{bar}</measure></part>' for n in range(1, staves + 1))
    return (f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>{names}</part-list>{body}'
            '</score-partwise>').encode()


def slurs_of(xml: bytes) -> list[tuple[str, str]]:
    """(the pitch step, start or stop) of each end of a slur, in the order of the music."""
    from xml.etree import ElementTree as ET
    return [(found.find("pitch/step").text, slur.get("type")) for found in ET.fromstring(xml).iter("note")
            for slur in found.iter("slur")]


def test_joining_pages_keeps_the_slurs_on_their_notes():
    joined = join_pages([slurred("C", "D"), slurred("E", "F")], "Obra")
    assert slurs_of(joined) == [("C", "start"), ("D", "stop"), ("E", "start"), ("F", "stop")]


def test_each_staff_keeps_its_own_slurs():
    joined = join_pages([slurred("C", "D", staves=3)], "Obra")
    assert len(slurs_of(joined)) == 6


def test_a_measure_without_slurs_stays_without_them():
    assert slurs_of(join_pages([page(2, 2)], "Obra")) == []


def test_the_parts_of_a_work_keep_their_slurs():
    combined = combine_parts([("Flauta", join_pages([slurred()], "x")), ("Oboe", join_pages([slurred("E", "F")], "x"))], "Obra")
    assert slurs_of(combined) == [("C", "start"), ("D", "stop"), ("E", "start"), ("F", "stop")]


def test_a_staff_taken_from_the_score_keeps_its_slurs():
    assert len(slurs_of(staff_of(join_pages([slurred(staves=2)], "Obra"), 1))) == 2


def test_a_work_music21_refuses_to_retouch_keeps_its_slurs(monkeypatch):
    """The second way of writing a work, with the notation as read (2026-10-28), keeps them too."""
    from music21.musicxml.xmlObjects import MusicXMLExportException
    from omr import merge

    class Refusing(merge.GeneralObjectExporter):
        def parse(self, *args, **kwargs):
            if self.makeNotation:
                raise MusicXMLExportException("a 2048th")
            return super().parse(*args, **kwargs)

    monkeypatch.setattr(merge, "GeneralObjectExporter", Refusing)
    assert slurs_of(join_pages([slurred()], "Obra")) == [("C", "start"), ("D", "stop")]
