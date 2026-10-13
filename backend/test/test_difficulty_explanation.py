"""Explaining the difficulty of a work (step 20, author's decision 2026-10-07): the explanation is
written only from ScoreLint's analysis, every reference it makes is checked against that evidence,
and without a real provider (or when it fails) a deterministic demo, never presented as AI, answers."""
from pathlib import Path

import pytest

from backend.analyzers.difficulty import compute_difficulty_score
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.difficulty_explanation import (EVIDENCE_VERSION, PROMPT_VERSION, difficulty_evidence,
                                                        explain_difficulty, validate_explanation, InvalidExplanation)
from backend.app.stored_scores import parsed_work
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


@pytest.fixture(scope="module")
def result():
    score = parsed_work((SCORES / "evaluation_study.musicxml").read_bytes())
    return {"title": "Estudio de evaluación", "composer": "Autora", "difficulty": compute_difficulty_score(score),
            "tempo": {"min_quarter_bpm": 120.0, "max_quarter_bpm": 120.0, "tempo_change_count": 0},
            "duration": {"seconds": 48, "assumed_tempo": False}, "parts": ["Flute", "Clarinet", "Tuba"]}


class Fake:
    """A provider that answers what the test says, or fails as told."""
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, answer=None, failure=None):
        self.answer, self.failure, self.calls = answer, failure, []

    def explain_difficulty(self, evidence):
        self.calls.append(evidence)
        if self.failure:
            raise self.failure
        return self.answer(evidence) if callable(self.answer) else self.answer


def valid_answer(evidence):
    passage = evidence["passages"][0]
    return {"summary": "La obra es de grado {} por la densidad rítmica a tempo vivo.".format(evidence["grade"]),
            "factors": [{"dimension": "density", "text": "Semicorcheas seguidas en el pasaje central.",
                         "instruments": [passage["instrument"]], "passages": [passage["id"]]}],
            "study_tip": "Estudiar el pasaje lento con metrónomo y subir poco a poco."}


def test_the_evidence_is_only_what_scorelint_measured_and_stays_small(result):
    evidence = difficulty_evidence(result)
    assert evidence["version"] == EVIDENCE_VERSION
    assert evidence["grade"] == result["difficulty"]["grade"] and evidence["grade_label"] == "Intermedio"
    assert evidence["scale"] == {"grades": 6, "technical_index_max": 10}
    assert {item["name"] for item in evidence["instruments"]} == {"Flute", "Clarinet", "Tuba"}
    first = evidence["instruments"][0]
    assert set(first) == {"name", "label", "family", "grade", "technical_index", "dimensions", "findings"}
    assert set(first["dimensions"]) == {"range", "register", "intervals", "density", "endurance", "tempo"}
    assert [item["id"] for item in evidence["passages"]] == ["P{}".format(i) for i in range(1, len(evidence["passages"]) + 1)]
    assert {"id", "instrument", "label", "measures", "findings"} <= set(evidence["passages"][0])
    assert evidence["passages"][0]["findings"][0]["label"]
    assert evidence["tempo"] == {"min_quarter_bpm": 120.0, "max_quarter_bpm": 120.0, "changes": 0}
    assert evidence["duration_seconds"] == 48
    assert "composer" not in evidence and "file_name" not in evidence, "only what explains the difficulty"


def test_the_demo_is_deterministic_valid_and_cites_real_passages(result):
    evidence = difficulty_evidence(result)
    demo = DemoExplanationProvider()
    first, again = demo.explain_difficulty(evidence), demo.explain_difficulty(evidence)
    assert first == again
    explanation = validate_explanation(first, evidence)
    assert explanation.summary.startswith("«Estudio de evaluación» tiene grado 4 (Intermedio)")
    assert 1 <= len(explanation.factors) <= 4
    assert any(factor.passages for factor in explanation.factors)


@pytest.mark.parametrize("change, reason", [
    (lambda answer: answer.pop("summary"), "summary"),
    (lambda answer: answer["factors"][0].update(dimension="armonía"), "dimension"),
    (lambda answer: answer["factors"][0].update(passages=["P99"]), "P99"),
    (lambda answer: answer["factors"][0].update(instruments=["Oboe"]), "Oboe"),
    (lambda answer: answer.update(factors=[]), "factors"),
    (lambda answer: answer.update(study_tip="x" * 2000), "study_tip"),
])
def test_an_answer_out_of_the_schema_or_citing_what_is_not_in_the_evidence_is_rejected(result, change, reason):
    evidence = difficulty_evidence(result)
    answer = valid_answer(evidence)
    change(answer)
    with pytest.raises(InvalidExplanation, match=reason):
        validate_explanation(answer, evidence)


def test_a_valid_answer_of_the_provider_is_shown_with_its_traceability(result):
    shown = explain_difficulty(result, Fake(valid_answer), DemoExplanationProvider())
    assert shown["mode"] == "llm" and shown["provider"] == "fake" and shown["model"] == "fake-model"
    assert shown["prompt_version"] == PROMPT_VERSION and shown["evidence_version"] == EVIDENCE_VERSION
    assert shown["fallback_reason"] is None
    assert shown["explanation"]["factors"][0]["passages"] == ["P1"]
    assert shown["passages"]["P1"]["measures"], "the browser can open each cited passage"


@pytest.mark.parametrize("provider, reason", [
    (Fake(failure=ProviderFailure("timeout")), "timeout"),
    (Fake(failure=ProviderFailure("rate_limit")), "rate_limit"),
    (Fake(failure=RuntimeError("boom")), "error"),
    (Fake({"summary": "sin factores"}), "invalid"),
    (Fake(lambda evidence: {**valid_answer(evidence), "factors": [{"dimension": "tempo", "text": "x",
                                                                    "instruments": [], "passages": ["P42"]}]}), "invalid"),
])
def test_when_the_provider_fails_the_demo_answers_and_says_why(result, provider, reason):
    shown = explain_difficulty(result, provider, DemoExplanationProvider())
    assert shown["mode"] == "demo" and shown["provider"] == "demo" and shown["model"] is None
    assert shown["fallback_reason"] == reason
    assert shown["explanation"]["summary"]


def test_without_a_real_provider_the_demo_answers_without_a_fallback_reason(result):
    shown = explain_difficulty(result, DemoExplanationProvider(), DemoExplanationProvider())
    assert shown["mode"] == "demo" and shown["fallback_reason"] is None


def test_an_analysis_without_instruments_is_still_explained(result):
    empty = {"title": "Vacía", "difficulty": {"grade": 1, "by_instrument": {}, "by_family": {}, "critical_passages": [],
                                               "scale": {"grades": 6, "technical_index_max": 10}}}
    shown = explain_difficulty(empty, DemoExplanationProvider(), DemoExplanationProvider())
    assert shown["explanation"]["factors"] and shown["passages"] == {}


def test_the_text_never_shows_internal_ids_or_part_names_in_english(result):
    """First answer of Gemini (2026-10-13): «como P3, P4 y P5» and «Concert Snare Drum». The ids and
    the MusicXML names belong in the citation fields; the director reads Spanish names."""
    evidence = difficulty_evidence(result)
    passage, instrument = evidence["passages"][0], evidence["instruments"][0]

    def answer(evidence):
        text = "Lo más difícil está en {} ({}); estudia {} despacio.".format(instrument["name"], passage["id"], passage["id"])
        return {**valid_answer(evidence), "summary": text, "study_tip": "Empieza por " + passage["id"] + "."}

    shown = explain_difficulty(result, Fake(answer), DemoExplanationProvider())["explanation"]
    readable = "{} (compases {})".format(passage["label"], passage["measures"])
    assert shown["summary"] == "Lo más difícil está en {} ({}); estudia {} despacio.".format(instrument["label"], readable, readable)
    assert shown["study_tip"] == "Empieza por " + readable + "."
    assert shown["factors"][0]["passages"] == [passage["id"]], "the citation fields keep the ids"
