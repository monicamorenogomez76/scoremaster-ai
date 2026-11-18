"""The marks of a score's structure (2026-11-18): the musical analysis of a work, as in a conservatory, needs where its
sections begin and end. Double and final barlines, repeats, first and second endings, rehearsal marks, written words
(«Trio», «D.C. al Fine», «Allegro»), segno and coda are kept measure by measure."""
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.score_codec import decode_score, encode_score

ATTRIBUTES = ("<attributes><divisions>1</divisions><key><fifths>-3</fifths></key><time><beats>2</beats><beat-type>4</beat-type>"
              "</time><clef><sign>G</sign><line>2</line></clef></attributes>")
NOTE = "<note><pitch><step>E</step><alter>-1</alter><octave>5</octave></pitch><duration>2</duration><type>half</type></note>"


def words(text: str) -> str:
    return f"<direction><direction-type><words>{text}</words></direction-type></direction>"


MEASURES = [
    ATTRIBUTES + '<direction><direction-type><rehearsal>A</rehearsal></direction-type></direction>' + words("Allegro") + NOTE
    + '<barline location="left"><repeat direction="forward"/></barline>',
    NOTE + '<barline location="right"><bar-style>light-heavy</bar-style><repeat direction="backward"/></barline>',
    '<barline location="left"><ending number="1" type="start"/></barline>' + NOTE
    + '<barline location="right"><ending number="1" type="stop"/><repeat direction="backward"/></barline>',
    '<barline location="left"><ending number="2" type="start"/></barline>' + NOTE
    + '<barline location="right"><bar-style>light-light</bar-style><ending number="2" type="discontinue"/></barline>',
    words("Trio") + '<direction><direction-type><segno/></direction-type></direction>' + NOTE,
    words("D.C. al Fine") + '<direction><direction-type><coda/></direction-type></direction>' + NOTE
    + '<barline location="right"><bar-style>light-heavy</bar-style></barline>',
]
SCORE = ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Flute'
         '</part-name></score-part></part-list><part id="P1">'
         + "".join(f'<measure number="{number}">{content}</measure>' for number, content in enumerate(MEASURES, 1))
         + "</part></score-partwise>")


def test_the_marks_of_the_structure_are_kept_measure_by_measure(tmp_path):
    path = tmp_path / "marks.musicxml"
    path.write_text(SCORE)
    first, second, third, fourth, fifth, sixth = parse_musicxml(path).parts[0].measures
    assert (first.rehearsal, first.words, first.repeat_start) == ("A", ("Allegro",), True)
    assert (second.barline, second.repeat_end) == ("light-heavy", True)
    assert (third.ending, third.repeat_end) == ("1", True)
    assert (fourth.ending, fourth.barline) == ("2", "light-light")
    assert (fifth.words, fifth.segno) == (("Trio",), True)
    assert (sixth.words, sixth.coda, sixth.barline) == (("D.C. al Fine",), True, "light-heavy")
    assert first.barline is None and not second.repeat_start and fifth.ending is None


def test_the_marks_survive_the_stored_model(tmp_path):
    path = tmp_path / "marks.musicxml"
    path.write_text(SCORE)
    score = parse_musicxml(path)
    assert decode_score(encode_score(score)) == score
