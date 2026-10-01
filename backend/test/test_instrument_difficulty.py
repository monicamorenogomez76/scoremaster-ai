from backend.analyzers.instrument_difficulty import (
    classify_instrument_family,
    compute_instrument_difficulty,
    instrument_label_es,
)
from backend.domain.models import ScoreMeasure, ScoreNote, ScorePart


def _part(name: str, pitches: tuple[str, ...]) -> ScorePart:
    return ScorePart(
        name=name,
        measures=(
            ScoreMeasure(
                number=1,
                notes=tuple(ScoreNote(pitch, 2.0) for pitch in pitches),
            ),
        ),
    )


def test_instrument_family_uses_musical_instrument_not_ambiguous_substrings():
    assert classify_instrument_family("Concert Bass Drum") == "percussion"
    assert classify_instrument_family("Double Bass") == "strings"
    assert classify_instrument_family("Bassoon") == "woodwinds"
    assert classify_instrument_family("Alto Saxophone") == "woodwinds"
    assert classify_instrument_family("Euphonium") == "brass"


def test_instrument_labels_only_name_a_transposition_when_the_score_does():
    assert instrument_label_es("Clarinet") == "Clarinete"
    assert instrument_label_es("B♭ Clarinet") == "Clarinete en Si bemol"


def test_instrument_difficulty_uses_each_instruments_register_profile():
    high_tuba = compute_instrument_difficulty(_part("Tuba", ("C6", "D6")))
    high_flute = compute_instrument_difficulty(_part("Flute", ("C6", "D6")))

    assert high_tuba["grade"] > high_flute["grade"]
    assert 1 <= high_tuba["grade"] <= 5
    assert 1 <= high_flute["grade"] <= 5


def test_instrument_difficulty_increases_for_extreme_register_in_same_instrument():
    comfortable = compute_instrument_difficulty(_part("Flute", ("C5", "D5")))
    extreme = compute_instrument_difficulty(_part("Flute", ("C7", "D7")))

    assert extreme["grade"] > comfortable["grade"]


def test_grade_five_is_reserved_for_extreme_technical_demand():
    measures = tuple(
        ScoreMeasure(
            number=number,
            notes=tuple(ScoreNote(pitch, 0.25) for pitch in ("C2", "C7") * 4),
        )
        for number in range(1, 11)
    )
    extreme_part = ScorePart(name="Flute", measures=measures)

    result = compute_instrument_difficulty(extreme_part, tempo_bpm=300)

    assert result["grade"] == 5
    assert result["difficulty_score"] == 5.0