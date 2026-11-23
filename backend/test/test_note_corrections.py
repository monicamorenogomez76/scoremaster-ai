"""The director corrects a note the PDF reader got wrong (2026-11-22, «1812» measures 81-83: the middle note of a triplet
read as a rest, a B natural read for a B flat). The correction changes the MusicXML, and the prepared model and audio
timeline are changed the same way, so a large work is never read with music21 again on Render: each patched result must
be what reading the corrected file would give."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.note_corrections import (
    CannotCorrect, NoteCorrection, correct_musicxml, correct_score, correct_timeline, undone)
from backend.parsers.playback import _decode, encode_timeline

TRIPLET = '<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>'


def pitch(step, octave, alter=0):
    return f"<pitch><step>{step}</step>{f'<alter>{alter}</alter>' if alter else ''}<octave>{octave}</octave></pitch>"


def note(content, duration, kind, extra=""):
    return f"<note>{content}<duration>{duration}</duration><voice>1</voice><type>{kind}</type>{extra}</note>"


def work(transpose=True) -> bytes:
    """A clarinet in B flat, 2/4, divisions 6: a triplet with a rest in the middle, then B natural and a chord."""
    attributes = ("<attributes><divisions>6</divisions><key><fifths>0</fifths></key><time><beats>2</beats>"
                  "<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef>"
                  + ("<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>" if transpose else "")
                  + "</attributes>")
    first = (note(pitch("C", 5), 2, "eighth", TRIPLET) + note("<rest/>", 2, "eighth", TRIPLET)
             + note(pitch("E", 5), 2, "eighth", TRIPLET) + note(pitch("G", 5), 6, "quarter"))
    second = (note(pitch("B", 4), 6, "quarter") + note(pitch("C", 5), 6, "quarter")
              + note("<chord/>" + pitch("E", 5), 6, "quarter"))
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list><score-part id="P1">'
            '<part-name>Clarinet in Bb</part-name></score-part></part-list><part id="P1">'
            f'<measure number="1">{attributes}{first}</measure><measure number="2">{second}</measure>'
            '</part></score-partwise>').encode()


def parsed(content: bytes):
    with TemporaryDirectory() as folder:
        path = Path(folder) / "work.musicxml"
        path.write_bytes(content)
        return parse_musicxml(path)


REST_TO_D = NoteCorrection(part_id="P1", measure=1, offset=1 / 3, old=None, new=("D", 0, 5))
B_TO_B_FLAT = NoteCorrection(part_id="P1", measure=2, offset=0.0, old=("B", 0, 4), new=("B", -1, 4))
CHORD_E_TO_F_SHARP = NoteCorrection(part_id="P1", measure=2, offset=1.0, old=("E", 0, 5), new=("F", 1, 5))
G_TO_REST = NoteCorrection(part_id="P1", measure=1, offset=1.0, old=("G", 0, 5), new=None)


@pytest.mark.parametrize("correction", [REST_TO_D, B_TO_B_FLAT, CHORD_E_TO_F_SHARP, G_TO_REST])
def test_the_model_and_the_audio_patched_are_what_reading_the_corrected_file_gives(correction):
    original = work()
    corrected = correct_musicxml(original, correction)
    assert corrected != original
    assert correct_score(parsed(original), correction) == parsed(corrected)
    patched = correct_timeline(encode_timeline(original), parsed(original), correction)
    assert rounded(_decode(patched)) == rounded(_decode(encode_timeline(corrected)))


def rounded(timeline):
    """The notes of each part: a note added where a rest was is timed by a sum, a float off music21's in the last digit."""
    return [(part.name, part.measures, [(round(item.onset, 9), round(item.release, 9), item.pitches, item.drums)
                                        for item in part.notes]) for part in timeline.parts]


def test_the_corrected_file_shows_the_accidental_of_the_new_note():
    corrected = correct_musicxml(work(), B_TO_B_FLAT).decode()
    assert "<alter>-1</alter>" in corrected and "<accidental>flat</accidental>" in corrected
    back = correct_musicxml(correct_musicxml(work(), B_TO_B_FLAT), undone(B_TO_B_FLAT)).decode()
    assert "<accidental>natural</accidental>" in back, "an accidental the director changed stays written"


def test_undoing_a_correction_gives_the_reading_back():
    for correction in (REST_TO_D, B_TO_B_FLAT, G_TO_REST):
        again = correct_musicxml(correct_musicxml(work(), correction), undone(correction))
        assert parsed(again) == parsed(work())


def test_a_note_that_is_not_there_is_never_guessed():
    with pytest.raises(CannotCorrect):
        correct_musicxml(work(), NoteCorrection(part_id="P1", measure=1, offset=0.0, old=("D", 0, 5), new=("E", 0, 5)))
    with pytest.raises(CannotCorrect):
        correct_musicxml(work(), NoteCorrection(part_id="P9", measure=1, offset=0.0, old=("C", 0, 5), new=("D", 0, 5)))
    with pytest.raises(CannotCorrect):
        correct_musicxml(work(), NoteCorrection(part_id="P1", measure=7, offset=0.0, old=("C", 0, 5), new=("D", 0, 5)))
    with pytest.raises(CannotCorrect, match="acorde"):
        correct_musicxml(work(), NoteCorrection(part_id="P1", measure=2, offset=1.0, old=("E", 0, 5), new=None))


def test_the_notes_of_a_measure_are_listed_as_a_correction_names_them():
    from backend.parsers.note_corrections import measure_notes, note_parts
    assert note_parts(work()) == [{"id": "P1", "name": "Clarinet in Bb"}]
    found = measure_notes(work(), "P1", "1")
    assert found["measure"] == 1 and found["number"] == "1"
    assert [(round(item["offset"], 3), item["pitch"], item["type"], item["chord"]) for item in found["notes"]] == [
        (0.0, ["C", 0, 5], "eighth", False), (0.333, None, "eighth", False), (0.667, ["E", 0, 5], "eighth", False),
        (1.0, ["G", 0, 5], "quarter", False)]
    assert [item["chord"] for item in measure_notes(work(), "P1", "2")["notes"]] == [False, False, True]
    assert measure_notes(work(), "P1", "9") is None and measure_notes(work(), "P9", "1") is None


# --- Durations (2026-11-23): a note shortened leaves a rest; lengthened, it takes what follows in its voice; never past
# the bar line. Each patched model and timeline is what reading the corrected file gives, and undoing gives the reading.

def plain() -> bytes:
    """A flute in 2/4, divisions 4: measure 1 four eighths C D E F; measure 2 a half note G; measure 3 a quarter chord
    C-E and a quarter rest."""
    eighth = lambda step: note(pitch(step, 5), 2, "eighth")
    attributes = ("<attributes><divisions>4</divisions><key><fifths>0</fifths></key><time><beats>2</beats>"
                  "<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>")
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list><score-part id="P1">'
            '<part-name>Flute</part-name></score-part></part-list><part id="P1">'
            f'<measure number="1">{attributes}{"".join(eighth(step) for step in "CDEF")}</measure>'
            f'<measure number="2">{note(pitch("G", 5), 8, "half")}</measure>'
            f'<measure number="3">{note(pitch("C", 5), 4, "quarter")}{note("<chord/>" + pitch("E", 5), 4, "quarter")}'
            f'{note("<rest/>", 4, "quarter")}</measure></part></score-partwise>').encode()


def lasting(position, offset, old, kind, dots=0):
    return NoteCorrection(part_id="P1", measure=position, offset=offset, old=old, new=old, new_type=kind, new_dots=dots)


DURATIONS = [
    lasting(1, 0.0, ("C", 0, 5), "quarter"),                 # takes D
    lasting(1, 0.0, ("C", 0, 5), "quarter", 1),              # takes D and E
    lasting(1, 0.5, ("D", 0, 5), "quarter", 1),              # takes E and F
    lasting(1, 0.0, ("C", 0, 5), "16th"),                    # leaves a 16th rest
    lasting(2, 0.0, ("G", 0, 5), "eighth"),                  # leaves rests: an eighth and a quarter
    lasting(2, 0.0, ("G", 0, 5), "quarter", 1),              # leaves an eighth rest
    lasting(3, 0.0, ("C", 0, 5), "half"),                    # the chord takes the rest
    lasting(3, 1.0, None, "eighth"),                         # a rest shortened
    lasting(1, 1.0, ("E", 0, 5), "quarter", 1),              # takes F and half of nothing: past the bar line
]


@pytest.mark.parametrize("correction", DURATIONS[:-1])
def test_a_duration_changed_gives_the_model_and_the_audio_of_the_corrected_file(correction):
    from backend.parsers.note_corrections import snapshot, restored
    original = plain()
    corrected = correct_musicxml(original, correction)
    model = parsed(original)
    assert correct_score(model, correction) == parsed(corrected)
    timeline = encode_timeline(original)
    patched = correct_timeline(timeline, model, correction)
    assert rounded(_decode(patched)) == rounded(_decode(encode_timeline(corrected)))
    # Undone from what the measure was before.
    kept = snapshot(original, model, timeline, correction)
    back, back_model, back_timeline = restored(corrected, parsed(corrected), patched, kept)
    assert parsed(back) == model and back_model == model
    assert rounded(_decode(back_timeline)) == rounded(_decode(timeline))


def test_a_duration_never_goes_past_the_bar_line_nor_into_a_tuplet():
    with pytest.raises(CannotCorrect, match="no cabe"):
        correct_musicxml(plain(), DURATIONS[-1])
    with pytest.raises(CannotCorrect, match="tresillo"):
        correct_musicxml(work(), NoteCorrection(part_id="P1", measure=1, offset=0.0, old=("C", 0, 5), new=("C", 0, 5),
                                                new_type="quarter"))
    shortened = correct_musicxml(plain(), DURATIONS[3]).decode()
    assert shortened.count("<type>16th</type>") == 2 and "<rest" in shortened
