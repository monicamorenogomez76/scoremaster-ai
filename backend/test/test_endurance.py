import pytest

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.endurance import longest_active_run, uninterrupted_passages
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart
from backend.rules.endurance import find_long_passages_without_rest


def active_bars(start, count):
    return tuple(ScoreMeasure(number, (ScoreNote("C4", 4),))
                 for number in range(start, start + count))


@pytest.mark.parametrize("count, expected", [(0, 0), (7, 0), (8, 1), (12, 1)])
def test_threshold_and_end_of_part(count, expected):
    part = ScorePart("Clarinet", active_bars(10, count))
    findings = find_long_passages_without_rest(Score("Continuity", (part,)))
    assert len(findings) == expected
    assert longest_active_run(part) == count
    if expected:
        assert findings[0].code == "SL005"
        assert findings[0].measure_range == f"10-{9 + count}"
        assert findings[0].evidence["measure_count"] == count


@pytest.mark.parametrize("events", [(), (ScoreNote(None, 4, True),),
    (ScoreNote("C4", 3.75), ScoreNote(None, .25, True))])
def test_empty_bars_and_even_short_rests_interrupt_continuity(events):
    part = ScorePart("Trumpet", active_bars(1, 8) +
                     (ScoreMeasure(9, events),) + active_bars(10, 8))
    passages = uninterrupted_passages(part)
    assert [item["measure_count"] for item in passages] == [8, 8]
    findings = find_long_passages_without_rest(Score("Two blocks", (part,)))
    assert [item.measure_range for item in findings] == ["1-8", "10-17"]


def test_analysis_includes_endurance_in_critical_passages_and_weight():
    score = Score("Sustained passage", (ScorePart("Clarinet", active_bars(1, 8)),))
    result = compute_difficulty_score(score)
    assert result["overall_score"] == 2
    assert result["by_instrument"]["Clarinet"]["findings"] == ["SL005"]
    assert result["critical_passages"][0]["measure_range"] == "1-8"
    assert result["critical_passages"][0]["findings"] == ["SL005"]


def test_unpitched_notes_count_as_activity_and_parts_are_independent():
    percussion = ScorePart("Snare Drum", tuple(
        ScoreMeasure(i, (ScoreNote(None, 4),)) for i in range(1, 9)))
    empty = ScorePart("Flute", ())
    findings = find_long_passages_without_rest(Score("Percussion", (empty, percussion)))
    assert [item.instrument for item in findings] == ["Snare Drum"]
