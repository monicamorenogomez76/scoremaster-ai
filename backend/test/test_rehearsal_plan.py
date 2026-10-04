"""Ensemble rehearsal plan: sectional blocks per common passage and a final tutti (step 15)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.analyzers.rehearsal_plan import MIN_BLOCK_MINUTES, build_rehearsal_plan
from backend.app.dependencies import get_analysis_repository
from backend.app.main import app
from backend.domain.models import PartMetadata, PartTransposition, Score, ScoreMeasure, ScoreNote, ScorePart

B_FLAT = PartMetadata(transposition=PartTransposition(-2, -1, 0))
FAMILIES = {"Clarinet 1": "woodwinds", "Clarinet 2": "woodwinds", "Alto Saxophone": "woodwinds",
            "Trumpet": "brass", "Flute": "woodwinds", "Tuba": "brass"}


def measures(pitch, count=24):
    return tuple(ScoreMeasure(number, (ScoreNote(pitch, 4.0),)) for number in range(1, count + 1))


def score(*names, metadata=None, count=24):
    return Score("Ensemble", tuple(ScorePart(name, measures("C5", count), (metadata or {}).get(name, PartMetadata()))
                                   for name in names))


def difficulty(*passages):
    return {"critical_passages": [{"instrument": i, "measure_range": r, "score": s, "findings": ["SL003"]}
                                  for i, r, s in passages],
            "by_instrument": {name: {"family": family} for name, family in FAMILIES.items()}}


def sectional(plan):
    return [block for block in plan["segments"] if block["type"] in ("sectional", "common")]


LINE = ["C3", "D3", "E3", "F3"]
TENOR_SAX = PartMetadata(transposition=PartTransposition(-2, -1, -1))


def written(name, pitches, metadata=PartMetadata(), count=24):
    """One bar repeated; the number of pitches fixes the rhythm (4 quarters, 2 halves, 1 whole, 8 eighths)."""
    duration = 4.0 / len(pitches)
    return ScorePart(name, tuple(ScoreMeasure(number, tuple(ScoreNote(pitch, duration) for pitch in pitches))
                                 for number in range(1, count + 1)), metadata)


def blocks(plan, kind):
    return [block for block in plan["segments"] if block["type"] == kind]


def test_who_plays_the_same_line_rehearses_first_then_subsections_with_the_rest():
    ensemble = Score("Ensemble", (
        written("Euphonium", LINE), written("Trombone", LINE), written("Tenor Saxophone", ["D4", "E4", "F#4", "G4"], TENOR_SAX),
        written("Clarinet 1", ["G4", "C5"]), written("Flute", ["C6"]),
    ))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Euphonium", "1-4", 4), ("Clarinet 1", "1-4", 2), ("Flute", "2-4", 2)))

    assert [(block["type"], block.get("group"), block["parts"]) for block in plan["segments"][:-1]] == [
        ("common", None, ["Euphonium", "Tenor Saxophone", "Trombone"]),
        ("sectional", "clarinets", ["Clarinet 1"]),
        ("sectional", "flutes", ["Flute"]),
    ]
    assert blocks(plan, "common")[0]["kind"] == "line"
    assert blocks(plan, "common")[0]["measure_range"] == "1-4"
    assert plan["segments"][-1]["type"] == "tutti"


def test_subsections_follow_the_rehearsal_groups_of_the_catalog():
    # Four different rhythms: nobody shares material, so every part rehearses in its subsection.
    ensemble = Score("Low voices", (written("Bassoon", ["C3", "E3", "G3", "C4"]), written("Tuba", ["C2", "G2"]),
                                    written("Horn in F", ["G4"]), written("Trumpet", ["C5", "D5", "E5", "F5", "G5", "F5", "E5", "D5"])))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Bassoon", "1-4", 3), ("Tuba", "1-4", 2), ("Horn in F", "1-4", 2),
                                                         ("Trumpet", "1-4", 2)))

    assert [(block["group"], block["parts"]) for block in blocks(plan, "sectional")] == [
        ("high_brass", ["Horn in F", "Trumpet"]), ("low_voices", ["Bassoon", "Tuba"])]


def test_the_tutti_joins_passages_with_common_lines_or_several_subsections():
    ensemble = Score("Join", (written("Euphonium", LINE), written("Trombone", LINE), written("Flute", ["C6", "G5"])))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Euphonium", "1-4", 3), ("Flute", "10-12", 1)))

    assert plan["segments"][-1]["measure_ranges"] == ["1-4"]


def test_the_tutti_is_always_last():
    plan = build_rehearsal_plan(score("Flute"), 30, difficulty(("Flute", "1-2", 2)))

    assert plan["segments"][-1]["type"] == "tutti"


@pytest.mark.parametrize("minutes", [10, 15, 30, 60, 90])
def test_the_plan_never_exceeds_the_available_time(minutes):
    passages = [("Clarinet 1" if index % 2 else "Tuba", "{}-{}".format(index * 20 + 1, index * 20 + 4), 10 - index)
                for index in range(8)]
    plan = build_rehearsal_plan(score("Clarinet 1", "Tuba", count=160), minutes, difficulty(*passages))

    planned = sum(block["minutes"] for block in plan["segments"])
    assert planned <= minutes
    assert plan["planned_minutes"] == planned
    assert all(block["minutes"] >= MIN_BLOCK_MINUTES for block in sectional(plan))
    kept = len(sectional(plan))
    assert kept + len(plan["omitted"]) == 8
    assert all(item["reason"] == "time" for item in plan["omitted"])


def test_higher_priority_passages_are_kept_when_time_is_short():
    # 10 minutes: 5 for the final tutti and room for a single 5-minute sectional block.
    plan = build_rehearsal_plan(score("Flute", "Tuba", count=40), 10, difficulty(("Flute", "1-2", 1), ("Tuba", "30-31", 9)))

    # Both parts hold the same whole notes, so the Tuba passage rehearses them together.
    assert [block["measure_range"] for block in sectional(plan)] == ["30-31"]
    assert [item["measure_range"] for item in plan["omitted"]] == ["1-2"]


def test_without_critical_passages_the_plan_is_a_single_tutti_reading():
    plan = build_rehearsal_plan(score("Flute", "Tuba"), 45, difficulty())

    assert plan["segments"] == [{"type": "tutti", "group": None, "parts": ["Flute", "Tuba"], "measure_ranges": ["1-24"],
                                 "minutes": 45, "findings": []}]
    assert plan["omitted"] == []


def test_the_plan_is_deterministic():
    arguments = (score("Clarinet 1", "Trumpet"), 60, difficulty(("Clarinet 1", "9-12", 2), ("Trumpet", "1-3", 5)))

    assert json.dumps(build_rehearsal_plan(*arguments)) == json.dumps(build_rehearsal_plan(*arguments))


def test_analyze_returns_the_ensemble_plan():
    class Repository:
        def save(self, record):
            return record.analysis_id
    app.dependency_overrides[get_analysis_repository] = Repository
    try:
        path = Path(__file__).resolve().parents[2] / "test-scores" / "high_density.musicxml"
        with path.open("rb") as musicxml:
            response = TestClient(app).post("/analyze", files={"file": ("high_density.musicxml", musicxml, "application/xml")},
                                            data={"total_minutes": "30"})
    finally:
        app.dependency_overrides.pop(get_analysis_repository, None)

    plan = response.json()["rehearsal_plan"]
    assert plan["total_minutes"] == 30
    assert plan["segments"][-1]["type"] == "tutti"
    assert plan["planned_minutes"] <= 30


def phrases(name, playing, count=30):
    """A part that plays quarters only in the given measures and rests elsewhere."""
    def bar(number):
        if number in playing:
            return tuple(ScoreNote(pitch, 1.0) for pitch in ["C5", "D5", "E5", "F5"])
        return (ScoreNote(None, 4.0, True),)
    return ScorePart(name, tuple(ScoreMeasure(number, bar(number)) for number in range(1, count + 1)))


def test_blocks_start_and_end_where_their_instruments_play():
    # The trumpet passage is c. 1-20, but the trumpets only play in c. 10-14.
    ensemble = Score("Rests", (phrases("Trumpet", range(10, 15)),))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Trumpet", "1-20", 3)))

    assert [block["measure_range"] for block in sectional(plan)] == ["10-14"]
    assert plan["segments"][-1]["measure_ranges"] == ["10-14"]


def test_a_long_silence_inside_a_block_splits_it_into_phrases():
    ensemble = Score("Phrases", (phrases("Trumpet", {1, 2, 15, 16}),))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Trumpet", "1-16", 3)))

    assert [block["measure_range"] for block in sectional(plan)] == ["1-2", "15-16"]


def test_short_rests_do_not_split_a_block():
    ensemble = Score("Breath", (phrases("Trumpet", {1, 2, 5, 6}),))
    plan = build_rehearsal_plan(ensemble, 60, difficulty(("Trumpet", "1-6", 3)))

    assert [block["measure_range"] for block in sectional(plan)] == ["1-6"]


def test_fractional_priorities_still_give_whole_minutes_within_the_budget():
    plan = build_rehearsal_plan(score("Flute", "Tuba", count=40), 47,
                                difficulty(("Flute", "1-2", 2.5), ("Tuba", "30-31", 6.25)))

    assert all(isinstance(block["minutes"], int) for block in plan["segments"])
    assert plan["planned_minutes"] == 47
