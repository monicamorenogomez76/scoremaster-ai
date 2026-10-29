"""Measures read from a PDF keep the length of their time signature (2026-10-29). copista sometimes reads a measure
too long or too short: a whole-measure rest followed by notes, a group of 32nd notes a little long, a note missing.
Every later measure of that part then sounded late or early against the band: in «Paco el barba» half the parts drifted
from one to sixteen beats. Each measure takes the length its time signature says."""
from music21 import converter, stream

from backend.parsers.pdf_measures import fit_measures

DIVISIONS = 4   # per quarter: a 2/4 measure is 8


def note(duration, step="C", rest=False, chord=False, voice=None):
    pitch = "<rest/>" if rest else f"<pitch><step>{step}</step><octave>5</octave></pitch>"
    return (f"<note>{'<chord/>' if chord else ''}{pitch}<duration>{duration}</duration>"
            f"{f'<voice>{voice}</voice>' if voice else ''}</note>")


def work(*measures: str, beats=2) -> bytes:
    attributes = (f"<attributes><divisions>{DIVISIONS}</divisions><time><beats>{beats}</beats><beat-type>4</beat-type>"
                  "</time><clef><sign>G</sign><line>2</line></clef></attributes>")
    body = "".join(f'<measure number="{n}">{attributes if n == 1 else ""}{content}</measure>'
                   for n, content in enumerate(measures, 1))
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list><score-part id="P1">'
            f'<part-name>Flute</part-name></score-part></part-list><part id="P1">{body}</part></score-partwise>').encode()


def layout(musicxml: bytes) -> list[tuple]:
    """(measure, offset in quarters, duration, notes as (offset in the measure, name or rest, duration))."""
    part = converter.parseData(musicxml.decode(), format="musicxml").parts[0]
    return [(int(m.number), float(m.offset), float(m.duration.quarterLength),
             [(float(n.offset), "rest" if n.isRest else n.pitch.name if n.isNote else ".".join(p.name for p in n.pitches),
               float(n.quarterLength)) for n in m.recurse().notesAndRests])
            for m in part.getElementsByClass(stream.Measure)]


def offsets(musicxml: bytes) -> list[float]:
    return [offset for _, offset, _, _ in layout(musicxml)]


def test_a_measure_too_long_keeps_its_length_and_the_next_ones_start_in_time():
    read = work(note(8), note(4) + note(4) + note(2) + note(2), note(8))
    assert offsets(read) == [0, 2, 5], "the second measure was read with three beats"
    fitted = fit_measures(read)
    assert offsets(fitted) == [0, 2, 4]
    assert layout(fitted)[1][3] == [(0, "C", 1), (1, "C", 1)], "what does not fit is cut"


def test_a_note_that_goes_past_the_bar_line_is_shortened():
    read = work("".join(note(1) for _ in range(7)) + note(2), note(8))
    fitted = fit_measures(read)
    assert offsets(fitted) == [0, 2]
    assert layout(fitted)[0][3][-1] == (1.75, "C", 0.25)


def test_a_whole_measure_rest_read_with_other_notes_is_dropped():
    """The case of trumpet 1 in measure 1 and of the flute in measure 30: the rest is the reader's mistake."""
    read = work(note(8, rest=True) + note(2, rest=True) + note(2, "D") + note(2, rest=True) + note(2, "E"), note(8))
    fitted = fit_measures(read)
    assert offsets(fitted) == [0, 2]
    assert [name for _, name, _ in layout(fitted)[0][3]] == ["rest", "D", "rest", "E"]


def test_a_measure_too_short_is_completed_with_silence():
    read = work(note(8), note(4), note(8))
    assert offsets(read) == [0, 2, 3]
    fitted = fit_measures(read)
    assert offsets(fitted) == [0, 2, 4]
    assert layout(fitted)[1][3][0] == (0, "C", 1), "the notes read stay where they were"


def test_a_short_first_measure_is_an_upbeat_completed_before_its_notes():
    fitted = fit_measures(work(note(2) + note(2), note(8)))
    assert offsets(fitted) == [0, 2]
    assert [(offset, name) for offset, name, _ in layout(fitted)[0][3] if name != "rest"] == [(1, "C"), (1.5, "C")]


def test_chords_and_voices_are_cut_at_the_bar_line_too():
    voices = (note(4, voice=1) + note(4, "E", chord=True, voice=1) + note(6, voice=1) + "<backup><duration>10</duration></backup>"
              + note(8, "G", voice=2) + note(4, "A", voice=2))
    fitted = fit_measures(work(voices, note(8)))
    assert offsets(fitted) == [0, 2]
    [(_, _, duration, notes)] = layout(fitted)[:1]
    assert duration == 2
    assert sorted(notes) == [(0, "C.E", 1), (0, "G", 2), (1, "C", 1)]


def test_measures_that_fit_and_works_already_fitted_are_left_as_they_are():
    good = work(note(4) + note(4), note(2) + note(6), beats=2)
    assert fit_measures(good) == good
    fitted = fit_measures(work(note(8), note(12)))
    assert fit_measures(fitted) == fitted


def test_a_change_of_time_signature_is_followed():
    three = ("<attributes><time><beats>3</beats><beat-type>4</beat-type></time></attributes>" + note(12))
    read = work(note(8), three, note(12) + note(4))
    assert offsets(fit_measures(read)) == [0, 2, 5]
    assert layout(fit_measures(read))[2][2] == 3
