"""Critical passage detector (step 14): may return zero passages and never cuts a melodic phrase."""
from pathlib import Path

from backend.analyzers.criticality import CriticalityPolicy, detect_critical_passages
from backend.analyzers.difficulty import compute_difficulty_score
from backend.domain.models import Finding, Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark
from backend.parsers.musicxml_parser import parse_musicxml

R = None
QUARTERS = [("C5", 1), ("D5", 1), ("E5", 1), ("F5", 1)]


def part(name="Flute", bars=16, rest_after=(), duration=None):
    """Quarters in every bar; a whole-bar rest in the given measures (strong phrase boundaries)."""
    def bar(number):
        notes = [(R, 4)] if number in rest_after else QUARTERS
        return ScoreMeasure(number, tuple(ScoreNote(p, d, p is None) for p, d in notes), duration)
    return ScorePart(name, tuple(bar(number) for number in range(1, bars + 1)))


def finding(code, measures, instrument="Flute"):
    return Finding(code, "warning", instrument, measures, "", {})


def ranges(passages):
    return [passage["measure_range"] for passage in passages]


def test_an_easy_piece_can_have_zero_critical_passages():
    score = Score("Easy", (part(),))
    assert detect_critical_passages(score, [finding("SL003", "5")]) == []


def test_a_peak_with_several_signals_is_critical_and_covers_its_whole_phrase():
    # Phrases: 1-7 and 9-16 (bar 8 is a whole-bar rest). The peak is in bars 10-11.
    score = Score("Peak", (part(rest_after={8}),))
    passages = detect_critical_passages(score, [finding("SL004", "10-11"), finding("SL002", "10"), finding("SL002", "11")])

    assert ranges(passages) == ["9-16"]
    assert passages[0]["core_range"] == "10-11"
    assert passages[0]["findings"] == ["SL002", "SL004"]
    assert "absolute" in passages[0]["signals"]


def test_uniform_difficulty_that_does_not_stand_out_is_not_critical():
    findings = [finding("SL002", str(n)) for n in range(1, 17)] + [finding("SL003", str(n)) for n in range(1, 17)]
    assert detect_critical_passages(Score("Uniform", (part(),)), findings) == []


def test_a_moderate_passage_that_stands_out_from_its_context_is_critical():
    score = Score("Relative", (part(rest_after={8}),))
    passages = detect_critical_passages(score, [finding("SL002", "12"), finding("SL003", "12")])

    assert ranges(passages) == ["9-16"]
    assert set(passages[0]["signals"]) == {"relative", "prominence"}


def test_a_single_kind_of_warning_is_not_enough_evidence():
    score = Score("One code", (part(rest_after={8}),))
    assert detect_critical_passages(score, [finding("SL004", "12"), finding("SL004", "13")]) == []


def test_a_peak_shorter_than_the_minimum_duration_is_not_critical():
    # One-beat bars: a two-measure peak lasts only two beats.
    score = Score("Short", (part(rest_after={8}, duration=1.0),))
    findings = [finding("SL004", "12-13"), finding("SL002", "12-13")]
    assert detect_critical_passages(score, findings) == []
    assert detect_critical_passages(score, findings, CriticalityPolicy(min_beats=2)) != []


def test_the_continuity_warning_is_evidence_but_does_not_make_a_peak():
    score = Score("Long run", (part(),))
    assert detect_critical_passages(score, [finding("SL005", "1-16")]) == []


def test_overlapping_passages_of_one_part_are_merged():
    score = Score("Two peaks", (part(rest_after={8}),))
    findings = [finding("SL004", "10"), finding("SL002", "10"), finding("SL004", "14"), finding("SL002", "14")]

    assert ranges(detect_critical_passages(score, findings)) == ["9-16"]


def test_difficulty_reports_the_new_passages_and_keeps_the_legacy_detector_for_the_baseline():
    score = parse_musicxml(Path(__file__).resolve().parents[2] / "test-scores" / "high_density.musicxml")

    current = compute_difficulty_score(score)
    legacy = compute_difficulty_score(score, critical_detector="legacy")

    assert all("core_range" in passage for passage in current["critical_passages"])
    assert all("core_range" not in passage for passage in legacy["critical_passages"])


SIXTEENTHS = [("C4", .25), ("D4", .25), ("E4", .25), ("F4", .25)] * 4


def runs(bpm, bars=4):
    """Stepwise sixteenths in every bar at the given quarter tempo."""
    measures = tuple(ScoreMeasure(n, tuple(ScoreNote(p, d) for p, d in SIXTEENTHS)) for n in range(1, bars + 1))
    return Score("Runs", (ScorePart("Clarinet", measures),), (TempoMark(1, 0, bpm, 1),))


def test_fast_runs_are_critical_even_with_a_single_kind_of_warning():
    # Sixteenths at 160: more than ten notes per second, during four bars.
    passages = detect_critical_passages(runs(160), [finding("SL003", "1-4", "Clarinet")])

    assert ranges(passages) == ["1-4"]
    assert "speed" in passages[0]["signals"]


def test_the_same_runs_at_a_slow_tempo_are_not_critical():
    assert detect_critical_passages(runs(60), [finding("SL003", "1-4", "Clarinet")]) == []


def test_a_fast_run_shorter_than_the_minimum_duration_is_not_critical():
    assert detect_critical_passages(runs(160, bars=4), [finding("SL003", "1-4", "Clarinet")],
                                    CriticalityPolicy(min_beats=20)) == []


def test_speed_follows_tempo_changes():
    score = runs(60, bars=8)
    faster = Score(score.title, score.parts, score.tempo_marks + (TempoMark(5, 0, 160, 1),))

    passages = detect_critical_passages(faster, [finding("SL003", "1-8", "Clarinet")])
    # Only bars 5-8 are fast; the passage still covers the whole phrase they belong to.
    assert [passage["core_range"] for passage in passages] == ["5-8"]
