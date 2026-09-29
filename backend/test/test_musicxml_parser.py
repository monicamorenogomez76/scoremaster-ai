from pathlib import Path

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