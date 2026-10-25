from pathlib import Path

from music21 import duration, metadata, note, stream, tempo

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


def test_parses_composer_metadata(tmp_path):
    score_stream = stream.Score()
    score_stream.metadata = metadata.Metadata()
    score_stream.metadata.title = "Persis Overture"
    score_stream.metadata.composer = "James L. Hosay"
    part = stream.Part()
    measure = stream.Measure(number=1)
    measure.append(note.Note("C4", quarterLength=1))
    part.append(measure)
    score_stream.append(part)
    score_path = tmp_path / "composer.musicxml"
    score_stream.write("musicxml", fp=score_path)

    score = parse_musicxml(score_path)

    assert score.composer == "James L. Hosay"


def test_numbers_repeated_instrument_staves_instead_of_merging_them(tmp_path):
    score_stream = stream.Score()
    for _ in range(3):
        part = stream.Part()
        part.partName = "B♭ Clarinet"
        measure = stream.Measure(number=1)
        measure.append(note.Note("C5", quarterLength=1))
        part.append(measure)
        score_stream.append(part)
    score_path = tmp_path / "clarinet-staves.musicxml"
    score_stream.write("musicxml", fp=score_path)

    score = parse_musicxml(score_path)

    assert [part.name for part in score.parts] == [
        "B♭ Clarinet 1",
        "B♭ Clarinet 2",
        "B♭ Clarinet 3",
    ]

def test_the_title_is_read_from_the_movement_title_too():
    """2026-10-14: a score with <movement-title> (as MuseScore and music21 write them) was shown as «Untitled
    score»: music21 keeps it as movementName and leaves title empty. Its best title is used."""
    from pathlib import Path
    scores = Path(__file__).resolve().parents[2] / "test-scores"
    assert parse_musicxml(scores / "evaluation_study.musicxml").title == "Evaluation Study"
    assert parse_musicxml(scores / "high_density.musicxml").title == "High Density Study", "work-title still works"
    assert parse_musicxml(scores / "high_register.musicxml").title == "Untitled score", "no title at all"


def test_reads_what_the_grading_guides_look_at(tmp_path):
    """difficulty-v3 (2026-10-25): the publishers' grading guides grade key signature, meter, tuplets,
    dynamics, articulation and ornaments, so the parser keeps them."""
    from music21 import articulations, dynamics, expressions, key, meter
    score_stream = stream.Score()
    part = stream.Part()
    first = stream.Measure(number=1)
    first.append(key.KeySignature(-3))
    first.append(meter.TimeSignature("4/4"))
    first.append(dynamics.Dynamic("mf"))
    accented = note.Note("E-4", quarterLength=1.0)
    accented.articulations = [articulations.Accent(), articulations.Staccato()]
    trilled = note.Note("F4", quarterLength=1.0)
    trilled.expressions = [expressions.Trill()]
    first.append([accented, trilled])
    for pitch in ("G4", "A-4", "B-4"):     # a quarter-note triplet: three in the time of two
        triplet = note.Note(pitch)
        triplet.duration = duration.Duration(2 / 3)
        triplet.duration.appendTuplet(duration.Tuplet(3, 2, "quarter"))
        first.append(triplet)
    second = stream.Measure(number=2)
    second.append(meter.TimeSignature("6/8"))
    second.append(dynamics.Dynamic("ff"))
    second.append(note.Note("C5", quarterLength=3.0))
    third = stream.Measure(number=3)
    third.append(note.Note("D5", quarterLength=3.0))
    part.append([first, second, third])
    score_stream.append(part)
    path = tmp_path / "guides.musicxml"
    score_stream.write("musicxml", fp=path)

    measures = parse_musicxml(path).parts[0].measures
    assert [measure.key_fifths for measure in measures] == [-3, -3, -3], "the key in force, also where it is not written"
    assert [measure.time_signature for measure in measures] == ["4/4", "6/8", "6/8"]
    assert [measure.dynamics for measure in measures] == [("mf",), ("ff",), ()]
    notes = measures[0].notes
    assert set(notes[0].articulations) == {"accent", "staccato"} and notes[0].ornaments == ()
    assert notes[1].ornaments == ("trill",)
    assert [item.tuplet for item in notes] == [False, False, True, True, True]


def test_a_part_without_key_or_meter_keeps_them_empty():
    score_path = Path(__file__).parents[2] / "test-scores" / "minimal.musicxml"
    measure = parse_musicxml(score_path).parts[0].measures[0]
    assert measure.dynamics == () and all(item.articulations == () and not item.tuplet for item in measure.notes)
