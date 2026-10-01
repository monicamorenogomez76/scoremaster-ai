from pathlib import Path

from music21 import duration, note, stream, tempo

from backend.parsers.musicxml_parser import parse_musicxml


def test_parses_part_measures_pitches_and_durations():
    score_path = Path(__file__).parents[2] / "test-scores" / "minimal.musicxml"

    score = parse_musicxml(score_path)

    assert score.title == "Synthetic Clarinet Study"
    assert len(score.parts) == 1

    part = score.parts[0]
    assert part.name == "Clarinet"
    assert len(part.measures) == 1
    assert part.measures[0].number == 1
    assert [(note.pitch, note.duration_quarters) for note in part.measures[0].notes] == [
        ("C4", 1.0),
        ("D4", 1.0),
    ]


def test_parses_multiple_measures_and_rest_events():
    score_path = Path(__file__).parents[2] / "test-scores" / "measure_with_rest.musicxml"

    score = parse_musicxml(score_path)

    assert score.title == "Rest and Measures Study"
    assert len(score.parts) == 1

    part = score.parts[0]
    assert [measure.number for measure in part.measures] == [1, 2]
    assert [(note.pitch, note.duration_quarters, note.is_rest) for note in part.measures[0].notes] == [
        ("C4", 1.0, False),
        (None, 1.0, True),
    ]
    assert [(note.pitch, note.duration_quarters, note.is_rest) for note in part.measures[1].notes] == [
        ("E4", 2.0, False),
    ]


def test_parses_numeric_tempo_marks_and_pulse_units(tmp_path):
    score_stream = stream.Score()
    part = stream.Part()
    first_measure = stream.Measure(number=1)
    first_measure.insert(0, tempo.MetronomeMark(number=72))
    first_measure.append(note.Note("C4", quarterLength=1))
    second_measure = stream.Measure(number=2)
    second_measure.insert(
        0,
        tempo.MetronomeMark(number=120, referent=duration.Duration(0.5)),
    )
    second_measure.append(note.Note("D4", quarterLength=1))
    part.append([first_measure, second_measure])
    score_stream.append(part)
    score_path = tmp_path / "tempo.musicxml"
    score_stream.write("musicxml", fp=score_path)

    score = parse_musicxml(score_path)

    assert score.parts[0].name == "Part 1"
    assert [
        (mark.measure_number, mark.offset_quarters, mark.beats_per_minute, mark.beat_unit_quarters)
        for mark in score.tempo_marks
    ] == [(1, 0.0, 72.0, 1.0), (2, 0.0, 120.0, 0.5)]


def test_parses_unpitched_percussion_attacks(tmp_path):
    score_stream = stream.Score()
    percussion_part = stream.Part()
    percussion_part.partName = "Concert Bass Drum"
    measure = stream.Measure(number=1)
    unpitched_note = note.Unpitched()
    unpitched_note.duration = duration.Duration(0.5)
    measure.append(unpitched_note)
    percussion_part.append(measure)
    score_stream.append(percussion_part)
    score_path = tmp_path / "percussion.musicxml"
    score_stream.write("musicxml", fp=score_path)

    score = parse_musicxml(score_path)

    assert score.parts[0].name == "Concert Bass Drum"
    assert [(event.pitch, event.duration_quarters, event.is_rest) for event in score.parts[0].measures[0].notes] == [
        (None, 0.5, False),
    ]