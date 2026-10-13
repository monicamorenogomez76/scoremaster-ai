"""Step 23: an AI explanation is asked once per evidence, provider, model and versions (2026-10-13: the
free quota of gemini-3.8-flash is 20 requests a day). Only valid AI answers are kept: never errors,
fallbacks or the demo."""
import pytest

from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.explanations import run_explanation
from backend.application.difficulty_explanation import DifficultyExplanation, validate_explanation
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider

EVIDENCE = {"version": "difficulty-evidence-v2", "title": "Obra", "grade": 3, "grade_label": "Intermedio",
            "grade_standard": "Grade 3", "grade_description": "Tres o cuatro años de práctica.",
            "instruments": [], "passages": [], "families": [], "scale": {}}
ANSWER = {"summary": "Grado 3.", "factors": [{"dimension": "general", "text": "Moderada."}], "study_tip": "Despacio."}


class Cache:
    def __init__(self):
        self.rows = {}

    def load(self, key):
        return self.rows.get(key)

    def save(self, key, value):
        self.rows[key] = value


class Llm:
    def __init__(self, answer=ANSWER, failure=None, model="m1"):
        self.info = ProviderInfo("llm", "gemini", model)
        self.answer, self.failure, self.calls = answer, failure, 0

    def explain_difficulty(self, evidence):
        self.calls += 1
        if self.failure:
            raise self.failure
        return self.answer


def explain(provider, cache, evidence=EVIDENCE, version="difficulty-explanation-v3"):
    return run_explanation(evidence, lambda who, data: who.explain_difficulty(data), validate_explanation,
                           provider, DemoExplanationProvider(), version, cache=cache)


def test_the_same_evidence_is_asked_once_and_then_read_from_the_cache():
    llm, cache = Llm(), Cache()
    first, again = explain(llm, cache), explain(llm, cache)
    assert llm.calls == 1
    assert (first["cached"], again["cached"]) == (False, True)
    assert again["explanation"] == first["explanation"] and again["mode"] == "llm" and again["model"] == "m1"


@pytest.mark.parametrize("change", [
    lambda: (Llm(model="m2"), EVIDENCE, "difficulty-explanation-v3"),
    lambda: (Llm(), {**EVIDENCE, "grade": 4}, "difficulty-explanation-v3"),
    lambda: (Llm(), EVIDENCE, "difficulty-explanation-v4"),
])
def test_another_model_evidence_or_prompt_asks_again(change):
    cache = Cache()
    explain(Llm(), cache)
    llm, evidence, version = change()
    assert explain(llm, cache, evidence, version)["cached"] is False and llm.calls == 1


def test_errors_fallbacks_and_the_demo_are_never_kept():
    cache = Cache()
    assert explain(Llm(failure=ProviderFailure("rate_limit")), cache)["fallback_reason"] == "rate_limit"
    assert explain(Llm({"summary": "sin factores"}), cache)["fallback_reason"] == "invalid"
    assert explain(DemoExplanationProvider(), cache)["mode"] == "demo"
    assert cache.rows == {}


def test_a_broken_cache_does_not_stop_the_explanation():
    class Broken:
        def load(self, key):
            raise RuntimeError("database down")

        def save(self, key, value):
            raise RuntimeError("database down")
    shown = explain(Llm(), Broken())
    assert shown["mode"] == "llm" and shown["cached"] is False


def test_a_kept_answer_that_no_longer_validates_is_asked_again():
    llm, cache = Llm(), Cache()
    explain(llm, cache)
    key = next(iter(cache.rows))
    cache.rows[key] = {"summary": "roto"}
    assert explain(llm, cache)["cached"] is False and llm.calls == 2
