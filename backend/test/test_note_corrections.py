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
