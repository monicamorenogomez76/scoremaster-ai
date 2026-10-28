"""Rehearsal series that prepares a concert (decided 2026-10-06): dates from a weekly
pattern, phases up to the concert with the general rehearsal last, more tutti as the concert comes
closer, the director's review changing the priorities, and works rotating when they do not fit."""
from datetime import date
from pathlib import Path

from backend.analyzers.concert_plan import ReviewedBlock, Slot, phases, plan_concert, rehearsal_dates
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_proposal import WorkToRehearse
from backend.parsers.musicxml_parser import parse_musicxml

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


def work(name, work_id):
    score = parse_musicxml(SCORES / name)
    return WorkToRehearse(work_id, name.split(".")[0], score, compute_difficulty_score(score))


def slots(*rehearsal_phases, minutes=90):
    return [Slot(date(2026, 10, 13 + index), "20:00", minutes, phase) for index, phase in enumerate(rehearsal_phases)]


def minutes_of(rehearsal, work_id, block_type=None):
    return sum(block["minutes"] for block in rehearsal["blocks"]
               if block["work_id"] == work_id and (block_type is None or block["type"] == block_type))


def test_rehearsal_dates_follow_the_weekly_pattern_until_the_day_before_the_concert():
    # Tuesday 13 to the concert on Thursday 29 October 2026, rehearsing on Tuesdays and Thursdays.
    assert rehearsal_dates(date(2026, 10, 13), date(2026, 10, 29), (1, 3)) == [
        date(2026, 10, 13), date(2026, 10, 15), date(2026, 10, 20), date(2026, 10, 22), date(2026, 10, 27)]
    assert rehearsal_dates(date(2026, 10, 30), date(2026, 10, 29), (1, 3)) == []


def test_the_series_goes_from_reading_to_the_general_rehearsal():
    assert phases(1) == ["general"]
    assert phases(2) == ["integration", "general"]
    assert phases(3) == ["reading", "integration", "general"]
    assert phases(6) == ["reading", "reading", "passages", "passages", "integration", "general"]


def test_the_general_rehearsal_runs_through_the_programme_in_concert_order():
    programme = [work("high_density.musicxml", "second"), work("high_register.musicxml", "first")]

    [general] = plan_concert(programme, slots("general"), [])

    assert general["blocks"][0]["type"] == "warmup"
    assert [(block["type"], block["work_id"]) for block in general["blocks"][1:]] == [("runthrough", "second"), ("runthrough", "first")]
    assert sum(block["minutes"] for block in general["blocks"]) == 90


def test_more_tutti_as_the_concert_comes_closer():
    programme = [work("high_register.musicxml", "w1")]

    reading, integration = plan_concert(programme, slots("reading", "integration"), [])

    assert minutes_of(integration, "w1", "tutti") > minutes_of(reading, "w1", "tutti")
    assert all(sum(block["minutes"] for block in item["blocks"]) == 90 for item in (reading, integration))


def test_a_passage_left_pending_gains_time_and_a_resolved_one_loses_it():
    programme = [work("high_register.musicxml", "w1"), work("high_density.musicxml", "w2")]
    [plain] = plan_concert(programme, slots("passages"), [])

    [after_pending] = plan_concert(programme, slots("passages"), [ReviewedBlock("w1", "1", "pending")])
    [after_resolved] = plan_concert(programme, slots("passages"), [ReviewedBlock("w1", "1", "resolved")])

    assert minutes_of(after_pending, "w1") > minutes_of(plain, "w1") > minutes_of(after_resolved, "w1")


def test_a_work_that_does_not_fit_is_rehearsed_first_next_time():
    programme = [work("high_register.musicxml", "w1"), work("high_density.musicxml", "w2"), work("large_intervals.musicxml", "w3")]

    first, second = plan_concert(programme, slots("passages", "passages", minutes=25), [])

    assert first["omitted_works"] == ["w3"]
    assert [block["work_id"] for block in second["blocks"] if block["work_id"]][0] == "w3"
