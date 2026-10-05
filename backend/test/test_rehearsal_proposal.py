"""Proposed agenda for a rehearsal of several works (2026-10-05): a warm-up for the whole band,
then each work with the ensemble plan of its own passages, its time proportional to its grade.
Every block names its work. Nothing is saved: the director reviews and edits the proposal."""
from pathlib import Path

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_proposal import MIN_WORK_MINUTES, WorkToRehearse, propose_rehearsal
from backend.parsers.musicxml_parser import parse_musicxml

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


def work(name, work_id, grade=None):
    score = parse_musicxml(SCORES / name)
    difficulty = compute_difficulty_score(score)
    if grade is not None:
        difficulty = {**difficulty, "grade": grade}
    return WorkToRehearse(work_id, name.split(".")[0], score, difficulty)


def test_a_rehearsal_starts_with_a_warm_up_and_names_the_work_of_every_block():
    proposal = propose_rehearsal([work("high_register.musicxml", "w1")], 60)

    warm_up, *blocks = proposal["blocks"]
    assert warm_up["type"] == "warmup" and warm_up["work_id"] is None and warm_up["minutes"] == 9
    assert blocks and all(block["work_id"] == "w1" and block["work_title"] == "high_register" for block in blocks)
    assert blocks[-1]["type"] == "tutti"
    assert sum(block["minutes"] for block in proposal["blocks"]) == 60


def test_the_time_of_each_work_is_proportional_to_its_grade():
    proposal = propose_rehearsal([work("high_register.musicxml", "easy", grade=2),
                                  work("high_density.musicxml", "hard", grade=4)], 90)

    allocation = {item["work_id"]: item["minutes"] for item in proposal["works"]}
    assert proposal["blocks"][0]["minutes"] == 14
    assert allocation == {"easy": 25, "hard": 51}
    for work_id, minutes in allocation.items():
        assert sum(block["minutes"] for block in proposal["blocks"] if block["work_id"] == work_id) == minutes
    assert [block["work_id"] for block in proposal["blocks"][1:]] == sorted(
        [block["work_id"] for block in proposal["blocks"][1:]], key=["easy", "hard"].index), "works keep their order"


def test_works_that_do_not_fit_are_reported_instead_of_squeezed():
    works = [work("high_register.musicxml", "w1"), work("high_density.musicxml", "w2"), work("large_intervals.musicxml", "w3")]

    proposal = propose_rehearsal(works, 25)

    planned = [item["work_id"] for item in proposal["works"]]
    assert planned == ["w1", "w2"]
    assert all(item["minutes"] >= MIN_WORK_MINUTES for item in proposal["works"])
    assert proposal["omitted_works"] == [{"work_id": "w3", "title": "large_intervals", "reason": "time"}]
    assert sum(block["minutes"] for block in proposal["blocks"]) == 25


def test_a_rehearsal_without_works_is_a_warm_up_and_nothing_else():
    proposal = propose_rehearsal([], 30)
    assert [block["type"] for block in proposal["blocks"]] == ["warmup"]
    assert proposal["blocks"][0]["minutes"] == 30
