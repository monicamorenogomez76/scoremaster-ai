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


def score(*names, metadata=None):
    return Score("Ensemble", tuple(ScorePart(name, measures("C5"), (metadata or {}).get(name, PartMetadata()))
                                   for name in names))


def difficulty(*passages):
    return {"critical_passages": [{"instrument": i, "measure_range": r, "score": s, "findings": ["SL003"]}
                                  for i, r, s in passages],
            "by_instrument": {name: {"family": family} for name, family in FAMILIES.items()}}


def sectional(plan):
    return [block for block in plan["segments"] if block["type"] == "sectional"]


def test_parts_of_one_section_in_the_same_measures_rehearse_together():
    plan = build_rehearsal_plan(score("Clarinet 1", "Clarinet 2", "Alto Saxophone"), 60,
                                difficulty(("Clarinet 1", "1-4", 4), ("Clarinet 2", "2-5", 2), ("Alto Saxophone", "3-4", 2)))

    [block] = sectional(plan)
    assert block["section"] == "woodwinds"
    assert block["parts"] == ["Alto Saxophone", "Clarinet 1", "Clarinet 2"]
    assert block["measure_range"] == "1-5"
    assert block["findings"] == ["SL003"]


def test_a_passage_shared_by_several_sections_gets_one_block_per_section_and_is_joined_in_the_tutti():
    plan = build_rehearsal_plan(score("Clarinet 1", "Trumpet"), 60,
                                difficulty(("Clarinet 1", "9-12", 2), ("Trumpet", "10-12", 2)))

    assert [(block["section"], block["parts"]) for block in sectional(plan)] == [
        ("brass", ["Trumpet"]), ("woodwinds", ["Clarinet 1"])]
    tutti = plan["segments"][-1]
    assert tutti["type"] == "tutti"
    assert tutti["measure_ranges"] == ["9-12"]


def test_cross_section_shared_material_is_reported_and_joined_in_the_tutti():
    # Both in B♭: the same written notes sound in unison.
    plan = build_rehearsal_plan(score("Clarinet 1", "Trumpet", metadata={"Clarinet 1": B_FLAT, "Trumpet": B_FLAT}), 60,
                                difficulty(("Clarinet 1", "5-6", 2)))

    tutti = plan["segments"][-1]
    assert {"parts": ["Clarinet 1", "Trumpet"], "kind": "unison", "measure_range": "5-6"} in tutti["shared"]
    assert tutti["measure_ranges"] == ["5-6"]


def test_the_tutti_is_always_last():
    plan = build_rehearsal_plan(score("Flute"), 30, difficulty(("Flute", "1-2", 2)))

    assert [block["type"] for block in plan["segments"]] == ["sectional", "tutti"]


@pytest.mark.parametrize("minutes", [10, 15, 30, 60, 90])
def test_the_plan_never_exceeds_the_available_time(minutes):
    passages = [("Clarinet 1" if index % 2 else "Tuba", "{}-{}".format(index * 20 + 1, index * 20 + 4), 10 - index)
                for index in range(8)]
    plan = build_rehearsal_plan(score("Clarinet 1", "Tuba"), minutes, difficulty(*passages))

    planned = sum(block["minutes"] for block in plan["segments"])
    assert planned <= minutes
    assert plan["planned_minutes"] == planned
    assert all(block["minutes"] >= MIN_BLOCK_MINUTES for block in sectional(plan))
    kept = len(sectional(plan))
    assert kept + len(plan["omitted"]) == 8
    assert all(item["reason"] == "time" for item in plan["omitted"])


def test_higher_priority_passages_are_kept_when_time_is_short():
    # 10 minutes: 5 for the final tutti and room for a single 5-minute sectional block.
    plan = build_rehearsal_plan(score("Flute", "Tuba"), 10, difficulty(("Flute", "1-2", 1), ("Tuba", "30-31", 9)))

    assert [block["parts"] for block in sectional(plan)] == [["Tuba"]]
    assert plan["omitted"][0]["parts"] == ["Flute"]


def test_without_critical_passages_the_plan_is_a_single_tutti_reading():
    plan = build_rehearsal_plan(score("Flute", "Tuba"), 45, difficulty())

    assert plan["segments"] == [{"type": "tutti", "section": None, "parts": ["Flute", "Tuba"], "measure_ranges": ["1-24"],
                                 "minutes": 45, "findings": [], "shared": []}]
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


def test_the_tutti_says_where_each_shared_material_is_and_lists_it_once():
    tutti_metadata = {"Clarinet 1": B_FLAT, "Trumpet": B_FLAT}
    plan = build_rehearsal_plan(score("Clarinet 1", "Trumpet", metadata=tutti_metadata), 60,
                                difficulty(("Clarinet 1", "5-6", 3), ("Trumpet", "20-21", 2)))

    shared = plan["segments"][-1]["shared"]
    assert shared == [{"parts": ["Clarinet 1", "Trumpet"], "kind": "unison", "measure_range": "5-6"},
                      {"parts": ["Clarinet 1", "Trumpet"], "kind": "unison", "measure_range": "20-21"}]
