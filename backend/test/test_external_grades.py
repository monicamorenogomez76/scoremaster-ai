"""Publisher grades of a work (PR 5 of the closing plan, 2026-10-14): typed in by the director with their
source, never extracted or asked to an LLM, which could invent them. Each keeps its original label and
its value on the app's 1-6 scale (docs/DIFFICULTY_CRITICALITY.md): Grade N is grade N with its halves,
and Pepper's letters VE, E, ME, M, MA and A are grades 1 to 6."""
import pytest

from backend.domain.difficulty_scale import external_grade


@pytest.mark.parametrize("scale, value, grade, label", [
    ("grade", "3", 3.0, "Grade 3"), ("grade", "3.5", 3.5, "Grade 3.5"), ("grade", "6", 6.0, "Grade 6"),
    ("grade", "0.5", 1.0, "Grade 0.5"), ("pepper", "VE", 1.0, "Pepper VE"), ("pepper", "me", 3.0, "Pepper ME"),
    ("pepper", "A", 6.0, "Pepper A"),
])
def test_a_published_grade_keeps_its_label_and_takes_its_place_on_the_scale(scale, value, grade, label):
    assert external_grade(scale, value) == (grade, label)


@pytest.mark.parametrize("scale, value", [("grade", "7"), ("grade", "3.25"), ("grade", "tres"), ("grade", "0"),
                                          ("pepper", "X"), ("abrsm", "5")])
def test_an_unknown_scale_or_value_is_refused(scale, value):
    with pytest.raises(ValueError):
        external_grade(scale, value)
