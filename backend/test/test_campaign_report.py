"""Step 19: the report compares ScoreLint's stored prediction with the musicians' ratings, reproducibly."""
import json

import pytest

from evaluation.campaign_report import (HEURISTIC, aggregate, build_report, critical_metrics, main, spearman,
                                        to_markdown)


def _passage(pid, grade, critical, family="Viento madera", work="Obra A"):
    return {"passage_id": pid, "work_id": work, "work_title": work, "parts": ["Flute"], "measure_range": "1-8",
            "snapshot": {"grade": grade, "technical_index": grade * 1.5, "family": family, "critical": critical,
                         "findings": [], "versions": {"scale": 2, "critical_detector": "phrases",
                                                      "sample": "evaluation-sample-v1"}}}


def _rating(pid, evaluator, difficulty, critical, level="amateur", priority=3):
    return {"passage_id": pid, "evaluator": evaluator, "experience_level": level, "main_instrument": "flauta",
            "difficulty": difficulty, "critical": critical, "priority": priority, "comment": ""}


EXPORT = {
    "campaign": {"id": "c1", "title": "Prueba", "status": "closed"},
    "passages": [_passage("p1", 2, False), _passage("p2", 4, True), _passage("p3", 5, True, "Metal", "Obra B"),
                 _passage("p4", 3, False, "Metal", "Obra B"), _passage("p5", 1, False)],
    "ratings": [_rating("p1", "Evaluador 1", 1, False), _rating("p1", "Evaluador 2", 3, False),
                _rating("p2", "Evaluador 1", 4, True), _rating("p2", "Evaluador 2", 5, True, "profesional"),
                _rating("p3", "Evaluador 1", 3, False), _rating("p3", "Evaluador 2", 4, True),
                _rating("p4", "Evaluador 1", 3, True), _rating("p4", "Evaluador 2", 3, True, "profesional")],
}


def test_spearman_uses_average_ranks_and_is_undefined_without_variation():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # Ties share their rank: ranks (1.5, 1.5, 3) against (1, 2, 3).
    assert spearman([1, 1, 2], [1, 2, 3]) == pytest.approx(0.8660254)
    assert spearman([2, 2, 2], [1, 2, 3]) is None
    assert spearman([1, 2], [1, 2]) is None


def test_expert_judgement_is_the_median_and_the_majority_and_ties_stay_undecided():
    rows = {row["passage_id"]: row for row in aggregate(EXPORT)["rows"]}
    assert rows["p1"]["expert_grade"] == 2 and rows["p1"]["grade_spread"] == 2
    assert rows["p2"]["expert_critical"] is True
    assert rows["p3"]["expert_critical"] is None, "one yes and one no is a tie, not a verdict"
    assert "p5" not in rows, "a passage nobody rated is left out"
    assert aggregate(EXPORT)["skipped"] == 1


def test_minimum_ratings_and_experience_filter():
    assert aggregate(EXPORT, min_ratings=3)["rows"] == []
    rows = aggregate(EXPORT, levels=["profesional"])["rows"]
    assert {row["passage_id"] for row in rows} == {"p2", "p4"}


def test_critical_metrics_weight_precision_and_report_undefined_values():
    metrics = critical_metrics([(True, True), (True, False), (False, True), (False, False)])
    assert (metrics["tp"], metrics["fp"], metrics["fn"], metrics["tn"]) == (1, 1, 1, 1)
    assert metrics["precision"] == metrics["recall"] == 0.5
    assert metrics["f05"] == pytest.approx(0.5)
    assert critical_metrics([(False, False)])["precision"] is None, "no positive prediction: precision undefined"
    skewed = critical_metrics([(True, True), (False, True), (False, True)])
    assert skewed["precision"] == 1.0 and skewed["recall"] == pytest.approx(1 / 3)
    assert skewed["f05"] > skewed["f1"], "F0.5 rewards precision more than F1"


def test_report_metrics_come_from_the_ratings():
    report = build_report(EXPORT)
    heuristic = report["methods"][HEURISTIC]
    # Predicted (2, 4, 5, 3) against medians (2, 4.5, 3.5, 3).
    assert heuristic["difficulty"]["n"] == 4
    assert heuristic["difficulty"]["mae"] == pytest.approx(0.5)
    assert heuristic["difficulty"]["bias"] == pytest.approx(0.25)
    # p3 is undecided; p1 (no, no) TN, p2 (yes, yes) TP, p4 (no, yes) FN.
    assert heuristic["undecided_critical"] == 1
    assert (heuristic["critical"]["tp"], heuristic["critical"]["fp"], heuristic["critical"]["fn"]) == (1, 0, 1)
    assert set(heuristic["by_work"]) == {"Obra A", "Obra B"}
    assert report["passages"]["evaluators"] == 2
    assert report["prediction_versions"]["critical_detector"] == ["phrases"]
    assert report["agreement"]["mean_pairwise_difference"] == pytest.approx(1.0)


def test_report_is_reproducible_and_never_names_the_musicians(tmp_path):
    source = tmp_path / "export.json"
    source.write_text(json.dumps(EXPORT), encoding="utf-8")
    outputs = []
    for run in range(2):
        target = tmp_path / f"report-{run}.json"
        assert main([str(source), "--json", str(target), "--markdown", str(tmp_path / f"report-{run}.md")]) == 0
        outputs.append((target.read_text(), (tmp_path / f"report-{run}.md").read_text()))
    assert outputs[0] == outputs[1]
    assert "| Heurística (ScoreLint) | 4 | 0.50 |" in outputs[0][1]
    assert "flauta" not in outputs[0][1]


def test_empty_campaign_produces_a_report_without_invented_figures():
    text = to_markdown(build_report({"campaign": {"title": "Vacía"}, "passages": [], "ratings": []}))
    assert "| Heurística (ScoreLint) | 0 | — |" in text
    assert "no se puede medir el acuerdo" in text
