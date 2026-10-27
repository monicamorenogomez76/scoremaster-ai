"""Passages proposed for the musicians' evaluation (decided 2026-10-07): a stratified,
reproducible sample of the director's works with critical AND non-critical passages, each with the
ScoreLint prediction for that very fragment, hidden from the musicians."""
from backend.analyzers.evaluation_sample import CRITICAL_SHARE, WorkSample, propose_passages
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark


def part(name, measures=40, pitch="C5", rest_from=None):
    bars = []
    for number in range(1, measures + 1):
        if rest_from and number >= rest_from:
            notes = (ScoreNote(None, 4.0, is_rest=True),)
        else:
            notes = tuple(ScoreNote(pitch, 0.5) for _ in range(8))
        bars.append(ScoreMeasure(number, notes, 4.0))
    return ScorePart(name, tuple(bars))


def work(work_id, critical_ranges=(), rest_from=None):
    score = Score(work_id, (part("Clarinet"), part("Flute", pitch="E5"), part("Tuba", pitch="C3", rest_from=rest_from)))
    passages = [{"instrument": "Clarinet", "measure_range": measures, "core_range": measures.split("-")[0] + "-" +
                 str(int(measures.split("-")[0]) + 1), "findings": ["SL003"]} for measures in critical_ranges]
    return WorkSample(work_id, work_id.title(), score, {"critical_passages": passages})


def span(passage):
    first, _, last = passage["measure_range"].partition("-")
    return int(first), int(last or first)


def test_the_sample_mixes_critical_and_non_critical_passages_from_every_work():
    works = [work("w1", ["5-14", "25-30"]), work("w2", ["9-12"]), work("w3", ["17-20", "33-36"])]

    passages = propose_passages(works, 20)

    assert len(passages) == 20
    critical = [item for item in passages if item["snapshot"]["critical"]]
    assert len(critical) == min(5, round(20 * CRITICAL_SHARE))
    assert {item["work_id"] for item in passages} == {"w1", "w2", "w3"}
    assert all(len(item["parts"]) == 1 and 4 <= span(item)[1] - span(item)[0] + 1 <= 12 for item in passages)


def test_non_critical_passages_avoid_the_critical_measures_and_silent_parts():
    passages = propose_passages([work("w1", ["5-14"], rest_from=10)], 12)

    for item in passages:
        first, last = span(item)
        if not item["snapshot"]["critical"] and item["parts"] == ["Clarinet"]:
            assert last < 5 or first > 14, "a non-critical window never overlaps a critical passage of its part"
        if item["parts"] == ["Tuba"]:
            assert last < 10, "a window where the part rests is not proposed"


def test_each_passage_keeps_the_scorelint_prediction_for_that_fragment():
    passages = propose_passages([work("w1", ["5-14"])], 6)
    passage = next(item for item in passages if item["snapshot"]["critical"])

    snapshot = passage["snapshot"]
    assert 1 <= snapshot["grade"] <= 6 and 0 <= snapshot["technical_index"] <= 10
    assert snapshot["critical"] is True and snapshot["findings"] == ["SL003"]
    assert set(snapshot["versions"]) == {"scale", "critical_detector", "sample", "difficulty"}
    assert snapshot["versions"]["difficulty"] == "difficulty-v5"   # 2026-10-27: graded by the Galician federation's table, ranges included
    assert passage["label"] == "Clarinet · cc. 5–8" and passage["measure_range"] == "5-8", "the core, widened to 4 measures"


def test_critical_passages_are_not_grouped_so_they_do_not_give_themselves_away():
    passages = propose_passages([work("w1", ["5-14", "25-30"]), work("w2", ["9-12", "33-36"])], 12)
    flags = [item["snapshot"]["critical"] for item in passages]
    assert flags != sorted(flags) and flags != sorted(flags, reverse=True)


def test_the_proposal_is_reproducible_and_never_larger_than_the_candidates():
    works = [work("w1", ["5-14"]), work("w2", ["9-12"])]
    assert propose_passages(works, 15) == propose_passages(works, 15)
    tiny = [WorkSample("w", "W", Score("w", (part("Clarinet", measures=8),)), {"critical_passages": []})]
    assert len(propose_passages(tiny, 50)) == 1


def test_non_critical_windows_alternate_between_works():
    works = [work("w1"), work("w2"), work("w3")]
    passages = propose_passages(works, 6)
    assert sorted(item["work_id"] for item in passages) == ["w1", "w1", "w2", "w2", "w3", "w3"], "a small sample takes from every work"


def test_a_passage_is_predicted_at_its_own_tempo():
    """difficulty-v2 (2026-10-14): the same notes in an andante are easier than in an allegro."""
    slow_then_fast = (TempoMark(1, 0.0, 60.0, 1.0), TempoMark(21, 0.0, 160.0, 1.0))
    sample = WorkSample("w", "W", Score("w", (part("Clarinet"),), slow_then_fast), {"critical_passages": [
        {"instrument": "Clarinet", "measure_range": "5-8", "core_range": "5-6", "findings": ["SL003"]},
        {"instrument": "Clarinet", "measure_range": "25-28", "core_range": "25-26", "findings": ["SL003"]}]})
    by_start = {span(item)[0]: item["snapshot"] for item in propose_passages([sample], 10) if item["snapshot"]["critical"]}
    assert by_start[5]["technical_index"] < by_start[25]["technical_index"]
