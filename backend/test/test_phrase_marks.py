"""Parser keeps note positions, bar lengths and written phrase marks for phrase detection."""
from backend.parsers.musicxml_parser import parse_musicxml


def write(tmp_path, notes, time="<time><beats>3</beats><beat-type>4</beat-type></time>"):
    path = tmp_path / "phrases.musicxml"
    path.write_text('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>'
                    '<score-part id="P1"><part-name>Flute</part-name></score-part></part-list><part id="P1">'
                    '<measure number="1"><attributes><divisions>2</divisions>' + time + '</attributes>' + notes +
                    '</measure></part></score-partwise>', encoding="utf-8")
    return path


def note(step, duration, extra=""):
    return ('<note><pitch><step>{}</step><octave>5</octave></pitch><duration>{}</duration>{}</note>').format(step, duration, extra)


def test_notes_know_their_offset_in_the_measure_and_bars_their_length(tmp_path):
    measure = parse_musicxml(write(tmp_path, note("C", 2) + '<note><rest/><duration>1</duration></note>' + note("D", 3))).parts[0].measures[0]

    assert [(n.pitch, n.offset_quarters) for n in measure.notes] == [("C5", 0.0), (None, 1.0), ("D5", 1.5)]
    assert measure.duration_quarters == 3.0


def test_breath_marks_caesuras_and_fermatas_are_phrase_marks(tmp_path):
    notes = (note("C", 2, "<notations><articulations><breath-mark/></articulations></notations>")
             + note("D", 2, "<notations><articulations><caesura/></articulations></notations>")
             + note("E", 1, "<notations><fermata/></notations>") + note("F", 1))
    measure = parse_musicxml(write(tmp_path, notes)).parts[0].measures[0]

    assert [n.phrase_mark for n in measure.notes] == [True, True, True, False]


def test_scores_built_by_hand_keep_working_without_positions():
    from backend.domain.models import ScoreMeasure, ScoreNote
    note_ = ScoreNote("C5", 1.0)
    assert (note_.offset_quarters, note_.phrase_mark) == (None, False)
    assert ScoreMeasure(1, (note_,)).duration_quarters is None
