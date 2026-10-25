"""ScoreLint without overrating (author's review, 2026-10-14). Real works came out one or two grades
above their publisher's grade (Persis: 6 against Grade 4) and the author's own (Oregon Trail II: 5 against
2): density counted notes per written beat whatever the tempo, took the busiest measure, endurance was
at its top after 16 bars, cornets fell to a generic profile and a busy snare drum raised the whole work.
«Los pasajes con muchas notas a velocidad lenta son fáciles o menos difíciles» (the author)."""
from backend.analyzers.difficulty import DIFFICULTY_VERSION, compute_difficulty_score
from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark

SCALE_NOTES = ("C5", "D5", "E5", "F5")


def running(name, measures, length=0.5, first=1, pitches=SCALE_NOTES):
    """Measures of 4/4 filled with notes of `length` crotchets."""
    count = int(4 / length)
    return tuple(ScoreMeasure(number=number, notes=tuple(ScoreNote(pitches[index % len(pitches)], length) for index in range(count)))
                 for number in range(first, first + measures))


def marks(*changes):
    return tuple(TempoMark(measure, 0.0, bpm, 1.0) for measure, bpm in changes)


def test_density_is_notes_per_second_at_the_tempo_of_the_passage():
    sixteenths = ScorePart("Flute", running("Flute", 8, 0.25))
    slow = compute_instrument_difficulty(sixteenths, tempo_marks=marks((1, 60)))
    fast = compute_instrument_difficulty(sixteenths, tempo_marks=marks((1, 160)))
    assert slow["dimensions"]["density"] < fast["dimensions"]["density"]
    assert "tempo" not in fast["dimensions"], "speed is inside notes per second: never counted twice"


def test_each_measure_takes_the_tempo_written_for_it():
    # The same semiquavers in the andante or in the allegro of one work.
    in_andante = ScorePart("Flute", running("Flute", 8, 0.25) + running("Flute", 8, 1.0, first=9))
    in_allegro = ScorePart("Flute", running("Flute", 8, 1.0) + running("Flute", 8, 0.25, first=9))
    tempi = marks((1, 60), (9, 160))
    assert compute_instrument_difficulty(in_andante, tempo_marks=tempi)["dimensions"]["density"] < \
        compute_instrument_difficulty(in_allegro, tempo_marks=tempi)["dimensions"]["density"]


def test_a_single_busy_measure_does_not_make_the_whole_part_dense():
    one_run = ScorePart("Flute", running("Flute", 1, 0.25) + running("Flute", 11, 1.0, first=2))
    all_runs = ScorePart("Flute", running("Flute", 12, 0.25))
    tempi = marks((1, 120))
    assert compute_instrument_difficulty(one_run, tempo_marks=tempi)["dimensions"]["density"] < 4
    assert compute_instrument_difficulty(all_runs, tempo_marks=tempi)["dimensions"]["density"] >= 8


def test_sixteen_bars_without_a_rest_are_ordinary_band_writing():
    sixteen = compute_instrument_difficulty(ScorePart("Trumpet", running("Trumpet", 16, 1.0)), tempo_marks=marks((1, 100)))
    thirty = compute_instrument_difficulty(ScorePart("Trumpet", running("Trumpet", 30, 1.0)), tempo_marks=marks((1, 100)))
    assert sixteen["dimensions"]["endurance"] < 8
    assert thirty["dimensions"]["endurance"] == 10


def test_cornet_and_flugelhorn_are_measured_as_trumpets():
    measures = running("x", 8, 0.5, pitches=("C5", "E5", "G5", "C6"))
    trumpet = compute_instrument_difficulty(ScorePart("Trumpet in Bb", measures), tempo_marks=marks((1, 112)))
    for name in ("B♭ Cornet 1", "Flugelhorn"):
        assert compute_instrument_difficulty(ScorePart(name, measures), tempo_marks=marks((1, 112)))["dimensions"] == trumpet["dimensions"], name


def test_the_legacy_scale_of_the_baseline_keeps_its_formula():
    legacy = compute_instrument_difficulty(ScorePart("Flute", running("Flute", 4, 0.25)), tempo_bpm=120, scale="legacy")
    assert "tempo" in legacy["dimensions"]


def _work(*parts, bpm=120):
    return Score("Work", tuple(parts), marks((1, bpm)))


def test_the_work_grade_comes_from_winds_and_strings_and_the_percussion_is_shown_apart():
    flute = ScorePart("Flute", running("Flute", 12, 2.0))
    snare = ScorePart("Snare Drum", running("Snare Drum", 12, 0.25, pitches=("C5",)))
    result = compute_difficulty_score(_work(flute, snare))
    families = result["by_family"]
    assert families["percussion"]["grade"] > families["woodwinds"]["grade"]
    assert result["grade"] == families["woodwinds"]["grade"]
    assert families["percussion"]["counts_for_work"] is False and families["woodwinds"]["counts_for_work"] is True


def test_a_work_for_percussion_alone_is_graded_by_its_percussion():
    snare = ScorePart("Snare Drum", running("Snare Drum", 12, 0.25, pitches=("C5",)))
    result = compute_difficulty_score(_work(snare))
    assert result["grade"] == result["by_family"]["percussion"]["grade"]
    assert result["by_family"]["percussion"]["counts_for_work"] is True


def test_the_result_names_the_version_of_its_algorithm():
    result = compute_difficulty_score(_work(ScorePart("Flute", running("Flute", 4, 1.0))))
    # difficulty-v3 (2026-10-25): the grade follows the publishers' guides.
    assert result["algorithm_version"] == DIFFICULTY_VERSION == "difficulty-v3"
    assert result["grade_method"] == "publisher_rubric"
