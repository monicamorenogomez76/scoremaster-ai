from pathlib import Path

from backend.analyzers import rehearsal_plan
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.domain.models import Score, ScoreMeasure, ScorePart
from backend.parsers.musicxml_parser import parse_musicxml


def test_build_rehearsal_plan_prioritizes_critical_sections():
    score_path = Path(__file__).parents[2] / "test-scores" / "high_density.musicxml"
    score = parse_musicxml(score_path)

    plan = build_rehearsal_plan(score, total_minutes=90)

    assert plan["total_minutes"] == 90
    assert len(plan["segments"]) >= 1
    assert plan["segments"][0]["priority"] == "high"
    assert plan["segments"][0]["measure_range"] == "1"


def test_build_rehearsal_plan_computes_findings_once_per_score(monkeypatch):
    score = Score(
        title="Two measures",
        parts=(
            ScorePart(
                name="Flute",
                measures=(ScoreMeasure(number=1, notes=()), ScoreMeasure(number=2, notes=())),
            ),
        ),
    )
    calls = 0

    def find_findings(_score):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(rehearsal_plan, "find_high_rhythm_density", find_findings)

    build_rehearsal_plan(score, total_minutes=30)

    assert calls == 1
