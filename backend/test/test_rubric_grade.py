"""difficulty-v3 (author's decision, 2026-10-25): ScoreLint follows the publishers' grading guides. Each criterion
of the American Band College chart (base), refined with FJH's series guidelines, gives a minimum grade; the work
is as hard as its most demanding criterion. A feature used only in passing (fewer than 5 % of a part's measures,
or a single measure) does not raise the grade, and end-of-year notes are accepted only when they are few."""
import pytest

from backend.analyzers.rubric_grade import rubric_grade
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark

CLARINET = PartMetadata(transposition=PartTransposition(-2, -1, 0))


def notes(*pitches, length=1.0, start=0.0, **extra):
    return tuple(ScoreNote(pitch, length, offset_quarters=start + index * length, **extra)
                 for index, pitch in enumerate(pitches))


def bars(count, content, key=-2, meter="4/4", dynamics=()):
    return tuple(ScoreMeasure(number, content, 4.0, key_fifths=key, time_signature=meter, dynamics=dynamics)
                 for number in range(1, count + 1))


def plain(pitch="D5", count=40, **bar_options):
    return bars(count, notes(pitch, pitch, pitch, pitch), **bar_options)


def work(*parts, tempo=None):
    marks = (TempoMark(1, 0.0, tempo, 1.0),) if tempo else ()
    return Score("Obra", tuple(parts), marks)


def criterion(result, name):
    return next(item for item in result["criteria"] if item["criterion"] == name)


def test_a_simple_work_in_b_flat_is_grade_1_and_says_why():
    result = rubric_grade(work(ScorePart("Flute", plain("D5")), tempo=100))
    assert result["grade"] == 1
    assert criterion(result, "key")["grade"] == 1 and criterion(result, "key")["source"] == "abc"
    assert all(item["grade"] <= 1 for item in result["criteria"])


@pytest.mark.parametrize("fifths, grade", [(-2, 1), (-3, 1), (0, 1), (-4, 2), (-5, 3), (-6, 4), (1, 4), (2, 5), (-7, 5)])
def test_the_concert_key_signature(fifths, grade):
    assert criterion(rubric_grade(work(ScorePart("Flute", plain(key=fifths)))), "key")["grade"] == grade


def test_a_transposing_part_is_read_in_concert_key():
    """A B-flat clarinet written in C plays in concert B-flat (grade 1), not in C."""
    result = rubric_grade(work(ScorePart("Clarinet in Bb", plain("D5", key=0), CLARINET)))
    assert criterion(result, "key")["value"] == -2 and criterion(result, "key")["grade"] == 1


@pytest.mark.parametrize("meter, grade", [("4/4", 1), ("2/2", 1), ("6/8", 2), ("9/8", 3), ("5/8", 4), ("7/4", 5)])
def test_the_meter(meter, grade):
    assert criterion(rubric_grade(work(ScorePart("Flute", plain(meter=meter)))), "meter")["grade"] == grade


def test_key_and_meter_changes():
    changing = bars(10, notes("D5", "D5", "D5", "D5")) + tuple(
        ScoreMeasure(10 + number, notes("D5", "D5", "D5", "D5"), 4.0, key_fifths=-3 if number % 2 else -2,
                     time_signature="3/4" if number % 2 else "4/4") for number in range(1, 9))
    result = rubric_grade(work(ScorePart("Flute", changing)))
    assert criterion(result, "key_changes")["value"] == 8 and criterion(result, "key_changes")["grade"] == 4
    assert criterion(result, "meter_changes")["value"] == 8 and criterion(result, "meter_changes")["grade"] == 4


@pytest.mark.parametrize("bpm, grade", [(100, 1), (132, 2), (144, 3), (160, 4), (190, 5), (60, 3), (50, 4)])
def test_the_tempo(bpm, grade):
    assert criterion(rubric_grade(work(ScorePart("Flute", plain()), tempo=bpm)), "tempo")["grade"] == grade


def test_without_tempo_marks_there_is_no_tempo_criterion():
    assert all(item["criterion"] != "tempo" for item in rubric_grade(work(ScorePart("Flute", plain())))["criteria"])


def test_the_length_of_the_work():
    """At crotchet = 100, 160 bars of 4/4 last 6 min 24 s: grade 3 (3 to 7 minutes)."""
    assert criterion(rubric_grade(work(ScorePart("Flute", plain(count=160)), tempo=100)), "length")["grade"] == 3


@pytest.mark.parametrize("pitch, grade", [("C6", 1), ("D6", 2), ("F6", 2), ("G6", 3), ("B-6", 4), ("C7", 5), ("D7", 6)])
def test_the_range_of_each_instrument_by_grade(pitch, grade):
    """The flute's written range: grade 1 reaches C6, grade 5 C7; beyond the chart is grade 6. D6 is grade 1 only as an
    end-of-year note now and then: in every bar it is grade 2."""
    many = bars(40, notes("D5", "D5", "D5", pitch))
    assert rubric_grade(work(ScorePart("Flute", many)))["by_instrument"]["Flute"]["grade"] == grade


def test_end_of_year_notes_are_accepted_only_when_few():
    """A clarinet in grade 1 stays below the break (B-flat 4); an end-of-year C5 now and then is still grade 1,
    the whole part over the break is grade 2."""
    once = bars(39, notes("D4", "D4", "D4", "D4")) + bars(1, notes("D4", "D4", "D4", "C5"))
    over = bars(40, notes("C5", "C5", "C5", "C5"))
    assert rubric_grade(work(ScorePart("Clarinet in Bb", once, CLARINET)))["by_instrument"]["Clarinet in Bb"]["grade"] == 1
    assert rubric_grade(work(ScorePart("Clarinet in Bb", over, CLARINET)))["by_instrument"]["Clarinet in Bb"]["grade"] == 2


def test_low_brass_is_read_at_concert_pitch():
    """The chart writes trombone, baritone and tuba in bass clef at concert pitch: a euphonium part written in
    treble clef (sounding a ninth lower) is compared by its sound."""
    treble = PartMetadata(transposition=PartTransposition(-14, -8, 0))
    part = ScorePart("Euphonium", bars(40, notes("E5", "E5", "E5", "E5")), treble)   # sounds D4
    assert rubric_grade(work(part))["by_instrument"]["Euphonium"]["grade"] == 1


@pytest.mark.parametrize("figure, grade", [(0.5, 1), (0.25, 2), (0.125, 3)])
def test_the_shortest_note_value(figure, grade):
    count = int(4 / figure)
    result = rubric_grade(work(ScorePart("Flute", bars(40, notes(*["D5"] * count, length=figure)))))
    assert result["by_instrument"]["Flute"]["criteria"]["note_values"]["grade"] == grade


def test_triplets_are_grade_2():
    triplet = notes("D5", "E5", "F5", length=1 / 3, tuplet=True) + notes("D5", "D5", "D5", start=1.0)
    part = ScorePart("Flute", bars(40, triplet))
    assert rubric_grade(work(part))["by_instrument"]["Flute"]["criteria"]["tuplets"]["grade"] == 2


def test_syncopation_by_meter_and_level():
    """An eighth-note syncopation in simple meter is grade 2; in compound meter grade 3; at the sixteenth, grade 5."""
    eighth = (ScoreNote("D5", 0.5, offset_quarters=0.0), ScoreNote("D5", 1.0, offset_quarters=0.5),
              ScoreNote("D5", 0.5, offset_quarters=1.5), ScoreNote("D5", 2.0, offset_quarters=2.0))
    compound = (ScoreNote("D5", 0.5, offset_quarters=0.0), ScoreNote("D5", 1.5, offset_quarters=0.5),
                ScoreNote("D5", 1.0, offset_quarters=2.0))
    sixteenth = (ScoreNote("D5", 0.25, offset_quarters=0.0), ScoreNote("D5", 0.5, offset_quarters=0.25),
                 ScoreNote("D5", 0.25, offset_quarters=0.75), ScoreNote("D5", 3.0, offset_quarters=1.0))
    grade = lambda measures: rubric_grade(work(ScorePart("Flute", measures)))["by_instrument"]["Flute"]["criteria"]["syncopation"]["grade"]
    assert grade(bars(40, eighth)) == 2
    assert grade(tuple(ScoreMeasure(n, compound, 3.0, key_fifths=-2, time_signature="6/8") for n in range(1, 41))) == 3
    assert grade(bars(40, sixteenth)) == 5


def test_a_feature_used_in_passing_does_not_raise_the_grade():
    """Sixteenths in one bar out of forty are a passing figure, not the grade of the part."""
    once = bars(39, notes("D5", "D5", "D5", "D5")) + bars(1, notes(*["D5"] * 16, length=0.25))
    assert rubric_grade(work(ScorePart("Flute", once)))["by_instrument"]["Flute"]["grade"] == 1


@pytest.mark.parametrize("marks, grade", [(("p", "f"), 1), (("mf",), 2), (("ff",), 3), (("sfz",), 3), (("fff",), 4)])
def test_the_dynamics(marks, grade):
    assert criterion(rubric_grade(work(ScorePart("Flute", plain(dynamics=marks)))), "dynamics")["grade"] == grade


def test_a_single_dynamic_mark_does_not_raise_the_grade():
    measures = plain() + (ScoreMeasure(41, notes("D5", "D5", "D5", "D5"), 4.0, key_fifths=-2, time_signature="4/4",
                                       dynamics=("fff",)),)
    assert criterion(rubric_grade(work(ScorePart("Flute", measures))), "dynamics")["grade"] == 1


@pytest.mark.parametrize("kind, marks, grade", [
    ("articulations", ("staccato", "accent"), 1), ("articulations", ("detached legato",), 2),
    ("articulations", ("tenuto",), 3), ("articulations", ("strong accent",), 4),
    ("ornaments", ("trill",), 2), ("ornaments", ("turn",), 4), ("ornaments", ("mordent",), 4)])
def test_articulations_and_ornaments(kind, marks, grade):
    part = ScorePart("Flute", bars(40, notes("D5", "D5", "D5", "D5", **{kind: marks})))
    assert rubric_grade(work(part))["by_instrument"]["Flute"]["criteria"][kind]["grade"] == grade


def test_grace_notes_single_and_in_groups():
    single = (ScoreNote("C5", 0.0, offset_quarters=0.0, is_grace=True),) + notes("D5", "D5", "D5", "D5")
    group = (ScoreNote("B4", 0.0, offset_quarters=0.0, is_grace=True),
             ScoreNote("C5", 0.0, offset_quarters=0.0, is_grace=True)) + notes("D5", "D5", "D5", "D5")
    grade = lambda content: rubric_grade(work(ScorePart("Flute", bars(40, content))))["by_instrument"]["Flute"]["criteria"]["grace_notes"]["grade"]
    assert grade(single) == 2 and grade(group) == 3


def test_the_work_is_as_hard_as_its_most_demanding_criterion_and_percussion_does_not_count():
    trumpet = ScorePart("Trumpet in Bb", bars(40, notes("C6", "D5", "D5", "D5")),
                        PartMetadata(transposition=PartTransposition(-2, -1, 0)))
    drums = ScorePart("Snare Drum", bars(40, notes(*["C5"] * 32, length=0.125)))
    result = rubric_grade(work(ScorePart("Flute", plain()), trumpet, drums, tempo=100))
    assert result["grade"] == 4, "the trumpet reaches C6"
    assert result["deciding"] == [{"criterion": "range", "instrument": "Trumpet in Bb", "grade": 4, "value": "C6", "source": "abc"}]
    assert "Snare Drum" not in result["by_instrument"], "percussion has no range or rhythm criteria in the guides"


def test_each_deciding_criterion_is_told_in_spanish_with_its_source():
    trumpet = ScorePart("Trumpet in Bb", bars(40, notes("C6", "D5", "D5", "D5")),
                        PartMetadata(transposition=PartTransposition(-2, -1, 0)))
    result = rubric_grade(work(trumpet, tempo=100))
    assert result["reasons_es"] == ["Tesitura de Trompeta en Si bemol hasta Do6 → grado 4 o más (American Band College)"]


@pytest.mark.parametrize("item, text", [
    ({"criterion": "key", "grade": 3, "value": -5, "source": "abc"}, "Armadura de concierto con 5 ♭ → grado 3 o más (American Band College)"),
    ({"criterion": "key", "grade": 5, "value": 5, "source": "abc"}, "Armadura de concierto con 5 ♯ → grado 5 o más (American Band College)"),
    ({"criterion": "meter_changes", "grade": 4, "value": 16, "source": "abc"}, "16 cambios de compás → grado 4 o más (American Band College)"),
    ({"criterion": "tempo", "grade": 4, "value": {"slowest": 48.0, "fastest": 132.0}, "source": "abc"},
     "Tempos de 48 a 132 pulsos por minuto → grado 4 o más (American Band College)"),
    ({"criterion": "length", "grade": 4, "value": 467, "source": "abc"}, "Duración de unos 8 minutos → grado 4 o más (American Band College)"),
    ({"criterion": "dynamics", "grade": 3, "value": ["ff", "pp"], "source": "abc"}, "Dinámicas ff y pp → grado 3 o más (American Band College)"),
    ({"criterion": "meter", "grade": 2, "value": "6/4", "source": "fjh"}, "Compás 6/4 → grado 2 o más (FJH)"),
    ({"criterion": "note_values", "instrument": "Flute", "grade": 4, "value": 0.0625, "source": "abc"},
     "Semifusas en Flauta → grado 4 o más (American Band College)"),
    ({"criterion": "ornaments", "instrument": "Flute", "grade": 4, "value": ["turn"], "source": "abc"},
     "Grupeto en Flauta → grado 4 o más (American Band College)"),
])
def test_the_spanish_reasons(item, text):
    from backend.analyzers.rubric_grade import reason_es
    assert reason_es(item, {"by_instrument": {}}) == text


def test_a_range_beyond_the_chart_says_so():
    from backend.analyzers.rubric_grade import reason_es
    rubric = {"by_instrument": {"Tuba": {"criteria": {"range": {"direction": "high"}}}}}
    item = {"criterion": "range", "instrument": "Tuba", "grade": 6, "value": "C4", "source": "abc"}
    assert reason_es(item, rubric) == "Tesitura de Tuba hasta Do4 → grado 6, por encima de la tabla (American Band College)"
