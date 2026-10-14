"""Step 13: visible grades 1-6 and an internal technical index 0-10.

Author's decisions (2026-10-05): the index is twice the previous 0-5 score and is split into six
equal bands; each grade describes the band that can play the part, without official certification.
"""
import pytest

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.domain.difficulty_scale import SCALE, grade_from_index, technical_index
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart


def _part(*pitches, name="Clarinet", quarters=0.25):
    notes = tuple(ScoreNote(pitch=pitch, duration_quarters=quarters) for pitch in pitches)
    return ScorePart(name=name, measures=(ScoreMeasure(number=1, notes=notes, duration_quarters=4.0),))


def test_the_technical_index_is_twice_the_previous_score_within_0_and_10():
    assert technical_index(2.61) == 5.22
    assert technical_index(-1.0) == 0.0
    assert technical_index(7.0) == 10.0


@pytest.mark.parametrize("index, grade", [
    (0.0, 1), (1.66, 1), (1.67, 2), (3.33, 2), (3.34, 3), (4.99, 3), (5.0, 4),
    (6.66, 4), (6.67, 5), (8.33, 5), (8.34, 6), (10.0, 6)])
def test_six_equal_bands_turn_the_index_into_a_grade(index, grade):
    assert grade_from_index(index) == grade


def test_an_instrument_reports_its_index_dimensions_and_grade_on_the_new_scales():
    legacy = compute_instrument_difficulty(_part("C4", "G5", "C4", "G5"), scale="legacy")
    current = compute_instrument_difficulty(_part("C4", "G5", "C4", "G5"))

    # difficulty-v2 (2026-10-14): the current scale no longer doubles the legacy score; it measures density
    # in notes per second and drops the separate tempo, so only the shared dimensions keep the transform.
    for key in ("range", "register", "intervals"):
        assert current["dimensions"][key] == technical_index(legacy["dimensions"][key])
    assert all(0 <= value <= 10 for value in current["dimensions"].values()) and "tempo" not in current["dimensions"]
    assert current["grade"] == grade_from_index(current["difficulty_score"])


def test_the_analysis_declares_its_scale_and_grades_families_on_it():
    score = Score(title="Scale", parts=(_part("C4", "G5", "C4", "G5"), _part("C3", "C3", name="Tuba", quarters=2.0)))

    result = compute_difficulty_score(score)

    assert result["scale"] == SCALE == {"version": 2, "grades": 6, "technical_index_max": 10}
    families = {family: details["grade"] for family, details in result["by_family"].items()}
    assert families == {details["family"]: grade_from_index(details["difficulty_score"])
                        for details in result["by_instrument"].values()}
    assert result["grade"] == max(families.values())


def test_the_legacy_scale_is_kept_for_the_baseline():
    score = Score(title="Scale", parts=(_part("C4", "G5", "C4", "G5"),))

    result = compute_difficulty_score(score, critical_detector="legacy", scale="legacy")

    assert "scale" not in result
    assert all(1 <= details["grade"] <= 5 and details["difficulty_score"] <= 5
               for details in result["by_instrument"].values())
