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


def _review(pid, grade, critical, model="gemini-3.8-flash", prompt="passage-review-v1"):
    return {"passage_id": pid, "provider": "gemini", "model": model, "prompt_version": prompt,
            "features_version": "passage-features-v1", "grade": grade, "critical": critical, "confidence": 0.7,
            "main_factors": ["rhythm"], "reason": "x", "created_at": "2026-10-13T10:00:00+00:00"}


def test_the_llm_gets_its_own_row_per_version_and_only_on_the_passages_it_reviewed():
    """Step 22, method B: one row per provider, model and prompt, so versions never mix."""
    export = {**EXPORT, "llm_reviews": [_review("p1", 2, False), _review("p2", 5, True), _review("p3", 4, False),
                                        _review("p1", 1, False, prompt="passage-review-v0")]}
    report = build_report(export)
    label = "LLM (gemini · gemini-3.8-flash · passage-review-v1)"
    other = "LLM (gemini · gemini-3.8-flash · passage-review-v0)"
    assert list(report["methods"]) == [HEURISTIC, label, other, "Híbrido (ScoreLint + LLM gemini · gemini-3.8-flash · passage-review-v1)",
                                       "Híbrido (ScoreLint + LLM gemini · gemini-3.8-flash · passage-review-v0)"]
    llm = report["methods"][label]
    assert llm["difficulty"]["n"] == 3, "p4 has no review with this version"
    # p1: 2 vs 2, p2: 5 vs 4.5, p3: 4 vs 3.5
    assert llm["difficulty"]["mae"] == pytest.approx((0 + 0.5 + 0.5) / 3)
    assert llm["critical"]["n"] == 2, "p3 is a tie and p4 was not reviewed"
    markdown = to_markdown(report)
    assert "| " + label + " | 3 |" in markdown


def test_the_hybrid_is_the_preregistered_rule_on_the_passages_with_both_predictions():
    """Step 24, method C, fixed on 2026-10-13 before any musician's rating: grade = mean of
    ScoreLint and the LLM rounding halves up; critical only when both say so. Never tuned on the data."""
    from evaluation.campaign_report import HYBRID_RULE, hybrid_grade
    assert (hybrid_grade(2, 3), hybrid_grade(2, 4), hybrid_grade(5, 6), hybrid_grade(1, 1)) == (3, 3, 6, 1)
    export = {**EXPORT, "llm_reviews": [_review("p1", 3, True), _review("p2", 5, True), _review("p3", 4, False)]}
    report = build_report(export)
    hybrid = "Híbrido (ScoreLint + LLM gemini · gemini-3.8-flash · passage-review-v1)"
    assert list(report["methods"])[-1] == hybrid
    rows = {row["passage_id"]: row["predicted"][hybrid] for row in report["rows"]}
    # p1: ScoreLint 2 / no + LLM 3 / yes → 3 / no; p2: 4 / yes + 5 / yes → 5 / yes; p3: 5 / yes + 4 / no → 5 / no
    assert rows["p1"] == {"grade": 3, "critical": False}
    assert rows["p2"] == {"grade": 5, "critical": True}
    assert rows["p3"] == {"grade": 5, "critical": False}
    assert rows["p4"] == {"grade": None, "critical": None}, "no LLM review: no hybrid"
    assert report["methods"][hybrid]["difficulty"]["n"] == 3
    assert "2026-10-13" in HYBRID_RULE and HYBRID_RULE in to_markdown(report)


def test_methods_are_also_compared_on_exactly_the_same_passages():
    """A method measured on other passages is not comparable: the fair table keeps only the passages
    that every method predicted (here p4 has no LLM review)."""
    export = {**EXPORT, "llm_reviews": [_review("p1", 3, True), _review("p2", 5, True), _review("p3", 4, False)]}
    report = build_report(export)
    common = report["same_passages"]
    assert common["passages"] == 3
    assert {name: metrics["difficulty"]["n"] for name, metrics in common["methods"].items()} == \
        {name: 3 for name in report["methods"]}
    # ScoreLint on p1, p2, p3: |2-2|, |4-4.5|, |5-3.5| → MAE 2/3
    assert common["methods"][HEURISTIC]["difficulty"]["mae"] == pytest.approx(2 / 3)
    assert "## Comparación en los mismos pasajes (3)" in to_markdown(report)


def test_the_report_compares_scorelint_with_the_publishers_work_by_work():
    """PR 5: one row per work with a published grade; several sources are averaged and listed. Spearman
    needs three works, and the report warns that a handful of works is a small sample."""
    from evaluation.campaign_report import build_report, to_markdown
    export = {"campaign": {"title": "x"}, "passages": [], "ratings": [], "llm_reviews": [], "works": [
        {"work_id": "1", "title": "Persis", "scorelint_grade": 6,
         "external_grades": [{"grade": 5.0, "label": "Grade 5", "source": "Editorial A"},
                             {"grade": 4.0, "label": "Pepper M", "source": "J.W. Pepper"}]},
        {"work_id": "2", "title": "Coral", "scorelint_grade": 2, "external_grades": [{"grade": 1.5, "label": "Grade 1.5", "source": "B"}]},
        {"work_id": "3", "title": "Marcha", "scorelint_grade": 4, "external_grades": [{"grade": 3.0, "label": "Grade 3", "source": "C"}]},
        {"work_id": "4", "title": "Sin grado", "scorelint_grade": 3, "external_grades": []},
    ]}
    report = build_report(export)["publishers"]
    assert [(row["title"], row["scorelint"], row["published"], row["difference"]) for row in report["works"]] == [
        ("Persis", 6, 4.5, 1.5), ("Coral", 2, 1.5, 0.5), ("Marcha", 4, 3.0, 1.0)]
    assert report["works"][0]["sources"] == "Grade 5 (Editorial A), Pepper M (J.W. Pepper)"
    assert report["n"] == 3 and report["mae"] == 1.0 and report["bias"] == 1.0 and report["spearman"] == 1.0
    assert report["without_grade"] == ["Sin grado"]
    text = to_markdown(build_report(export))
    assert "## Grado de la obra: ScoreLint frente a las editoriales" in text
    assert "| Persis | 6 | 4.5 | +1.5 | Grade 5 (Editorial A), Pepper M (J.W. Pepper) |" in text
    assert "muestra pequeña" in text


def test_without_published_grades_the_report_says_so():
    from evaluation.campaign_report import build_report, to_markdown
    export = {"campaign": {"title": "x"}, "passages": [], "ratings": [], "llm_reviews": []}
    assert build_report(export)["publishers"]["n"] == 0
    assert "Ninguna obra de la campaña tiene un grado publicado registrado." in to_markdown(build_report(export))
