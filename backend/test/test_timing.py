"""Step 10: musical timing and attacks — chords, ties, voices and grace notes.

Decided on 2026-10-05: a grace note is an extra attack; with several voices in one
staff, each voice is one player and the bar's density is that of its busiest voice.
"""
from music21 import chord, note, stream, tie

from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.analyzers.range import compute_range_metrics
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart
from backend.domain.timing import attack_count, is_attack, melodic_lines, measure_length, sounding_pitches
from backend.parsers.musicxml_parser import parse_musicxml
from backend.rules.high_density import find_high_rhythm_density
from backend.rules.large_intervals import find_large_intervals


def _parse(tmp_path, *measures):
    part = stream.Part()
    part.append(list(measures))
    score_stream = stream.Score()
    score_stream.append(part)
    path = tmp_path / "timing.musicxml"
    score_stream.write("musicxml", fp=path)
    return parse_musicxml(path).parts[0].measures


def _note(pitch, quarters=1.0, offset=None, voice=None, tie=None, grace=False, chord=()):
    return ScoreNote(pitch=pitch, duration_quarters=quarters, offset_quarters=offset,
                     voice=voice, tie=tie, is_grace=grace, chord_pitches=chord)


def _score(*notes, length=4.0):
    measure = ScoreMeasure(number=1, notes=tuple(notes), duration_quarters=length)
    return Score(title="Timing", parts=(ScorePart(name="Clarinet", measures=(measure,)),))


# Parser


def test_a_chord_is_one_event_with_all_its_pitches_and_the_top_note_as_pitch(tmp_path):
    measure = stream.Measure(number=1)
    measure.append(chord.Chord(["C4", "E4", "G4"], quarterLength=4))

    (parsed,) = _parse(tmp_path, measure)

    assert [(event.pitch, event.chord_pitches) for event in parsed.notes] == [("G4", ("C4", "E4", "G4"))]


def test_tied_notes_keep_their_tie(tmp_path):
    measure = stream.Measure(number=1)
    first, second = note.Note("C4", quarterLength=2), note.Note("C4", quarterLength=2)
    first.tie, second.tie = tie.Tie("start"), tie.Tie("stop")
    measure.append([first, second])

    (parsed,) = _parse(tmp_path, measure)

    assert [event.tie for event in parsed.notes] == ["start", "stop"]


def test_notes_keep_their_voice(tmp_path):
    measure = stream.Measure(number=1)
    upper, lower = stream.Voice(id="1"), stream.Voice(id="2")
    upper.append([note.Note("C5", quarterLength=2), note.Note("D5", quarterLength=2)])
    lower.append(note.Note("C4", quarterLength=4))
    measure.insert(0, upper)
    measure.insert(0, lower)

    (parsed,) = _parse(tmp_path, measure)

    assert [(event.pitch, event.voice, event.offset_quarters) for event in parsed.notes] == [
        ("C5", "1", 0.0), ("D5", "1", 2.0), ("C4", "2", 0.0)]


def test_grace_notes_are_marked_and_take_no_time(tmp_path):
    measure = stream.Measure(number=1)
    measure.append([note.Note("D4").getGrace(), note.Note("C4", quarterLength=4)])

    (parsed,) = _parse(tmp_path, measure)

    assert [(event.pitch, event.is_grace, event.duration_quarters) for event in parsed.notes] == [
        ("D4", True, 0.0), ("C4", False, 4.0)]


# Domain helpers


def test_a_tied_continuation_is_not_a_new_attack():
    assert is_attack(_note("C4", tie="start"))
    assert not is_attack(_note("C4", tie="continue"))
    assert not is_attack(_note("C4", tie="stop"))
    assert not is_attack(ScoreNote(pitch=None, duration_quarters=1.0, is_rest=True))


def test_attacks_count_a_chord_once_and_a_grace_note_as_an_extra_attack():
    measure = ScoreMeasure(number=1, notes=(
        _note("G4", chord=("C4", "E4", "G4")), _note("D4", 0.0, grace=True), _note("C4", 3.0, tie="start")))

    assert attack_count(measure) == 3


def test_attacks_of_several_voices_are_those_of_the_busiest_voice():
    measure = ScoreMeasure(number=1, notes=(
        *(_note("C5", 0.5, offset=index * 0.5, voice="1") for index in range(8)),
        _note("C4", 4.0, offset=0.0, voice="2")))

    assert attack_count(measure) == 8


def test_the_measure_length_is_the_bar_not_the_sum_of_its_voices():
    measure = ScoreMeasure(number=1, notes=(
        _note("C5", 4.0, offset=0.0, voice="1"), _note("C4", 4.0, offset=0.0, voice="2")))

    assert measure_length(measure) == 4.0


def test_melodic_lines_follow_each_voice_with_the_top_note_of_chords():
    measure = ScoreMeasure(number=1, notes=(
        _note("C5", 2.0, offset=0.0, voice="1"), _note("E5", 2.0, offset=2.0, voice="1", chord=("C5", "E5")),
        _note("C4", 2.0, offset=0.0, voice="2"), _note("C4", 2.0, offset=2.0, voice="2", tie="stop")))

    assert melodic_lines([measure]) == {"1": ["C5", "E5"], "2": ["C4"]}


def test_sounding_pitches_include_every_note_of_a_chord():
    assert sounding_pitches(_note("G4", chord=("C4", "E4", "G4"))) == ("C4", "E4", "G4")
    assert sounding_pitches(_note("C4")) == ("C4",)
    assert sounding_pitches(ScoreNote(pitch=None, duration_quarters=1.0, is_rest=True)) == ()


# Consumers


def test_a_sustained_tied_note_is_not_rhythmic_density():
    tied = (_note("C4", tie="start"), _note("C4", tie="continue"), _note("C4", tie="continue"),
            _note("C4", tie="stop"))

    assert find_high_rhythm_density(_score(*tied)) == []


def test_a_second_voice_does_not_dilute_the_density_of_the_first():
    alone = _score(*(_note("C5", offset=float(index), voice="1") for index in range(4)))
    with_pedal = _score(*(_note("C5", offset=float(index), voice="1") for index in range(4)),
                        _note("C4", 4.0, offset=0.0, voice="2"))

    assert [finding.evidence for finding in find_high_rhythm_density(with_pedal)] == \
        [finding.evidence for finding in find_high_rhythm_density(alone)]


def test_no_leap_is_reported_between_two_voices():
    two_voices = _score(_note("C5", 2.0, offset=0.0, voice="1"), _note("C5", 2.0, offset=2.0, voice="1"),
                        _note("C4", 2.0, offset=0.0, voice="2"), _note("C4", 2.0, offset=2.0, voice="2"))

    assert find_large_intervals(two_voices) == []


def test_the_range_includes_the_lower_notes_of_chords():
    metrics = compute_range_metrics(_score(_note("G4", chord=("C4", "E4", "G4"))))

    assert (metrics["min_pitch"], metrics["max_pitch"]) == ("C4", "G4")


def test_instrument_intervals_do_not_jump_between_voices():
    part = _score(_note("C6", 2.0, offset=0.0, voice="1"), _note("C6", 2.0, offset=2.0, voice="1"),
                  _note("C4", 2.0, offset=0.0, voice="2"), _note("C4", 2.0, offset=2.0, voice="2")).parts[0]

    assert compute_instrument_difficulty(part)["dimensions"]["intervals"] == 0.0
