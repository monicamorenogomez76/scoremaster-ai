"""PDF scores (author's decision, 2026-10-27): the reader in the Hugging Face Space (omr/) writes one MusicXML per
page; omr/merge.py joins the pages of a score staff by staff, and the parts read from several PDFs into one work."""
from xml.etree import ElementTree as ET

from backend.parsers.musicxml_parser import parse_musicxml
from omr.merge import combine_parts, join_pages


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
