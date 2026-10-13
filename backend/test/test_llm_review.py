"""Independent review of a passage by the LLM (step 22, method B): the same rubric and the same
critical question as the musicians, from measurements and notes only. Unlike the explanations there
is no demo: a rule-based stand-in would be another heuristic and would spoil the experiment."""
import json

import pytest

from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.llm_review import (InvalidReview, NotAvailable, PROMPT_VERSION, review_passage,
                                            validate_review)
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.infrastructure.ai.gemini_provider import GeminiExplanationProvider
from backend.infrastructure.ai.prompts import PASSAGE_REVIEW_PROMPT

FEATURES = {"version": "passage-features-v1", "instrument": "Flauta", "part": "Flute", "measures": "9-12",
            "tempo_quarter_bpm": 120.0, "notation": ["c.9: G5 semicorchea"]}
VALID = {"grade": 4, "critical": True, "confidence": 0.7, "main_factors": ["rhythm", "tempo"],
         "reason": "Semicorcheas continuas a negra = 120."}


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, answer=None, failure=None):
        self.answer, self.failure, self.seen = answer, failure, []

    def review_passage(self, features):
        self.seen.append(features)
        if self.failure:
            raise self.failure
        return self.answer


def test_a_valid_review_is_returned_with_its_traceability():
    reviewed = review_passage(FEATURES, Fake(VALID))
    assert reviewed == {**VALID, "provider": "fake", "model": "fake-model", "prompt_version": PROMPT_VERSION,
                        "features_version": "passage-features-v1"}


@pytest.mark.parametrize("change, field", [
    ({"grade": 7}, "grade"), ({"grade": 0}, "grade"), ({"confidence": 1.5}, "confidence"),
    ({"main_factors": ["armonía"]}, "main_factors"), ({"main_factors": []}, "main_factors"),
    ({"reason": "x" * 1000}, "reason"), ({"critical": "quizá"}, "critical"),
])
def test_answers_out_of_the_rubric_are_rejected(change, field):
    with pytest.raises(InvalidReview, match=field):
        validate_review({**VALID, **change})


def test_failures_are_reported_never_replaced_by_a_demo():
    with pytest.raises(ProviderFailure, match="timeout"):
        review_passage(FEATURES, Fake(failure=ProviderFailure("timeout")))
    with pytest.raises(InvalidReview):
        review_passage(FEATURES, Fake({"grade": 9}))
    with pytest.raises(NotAvailable):
        review_passage(FEATURES, DemoExplanationProvider())


def test_the_prompt_uses_the_musicians_rubric_and_never_scorelint():
    system = PASSAGE_REVIEW_PROMPT.system
    # v2 (2026-10-13): the rubric aligned with the Grade 1-6 scale of band publishers.
    assert PASSAGE_REVIEW_PROMPT.version == PROMPT_VERSION == "passage-review-v2"
    for level in ("Grade 1", "Primer año de instrumento", "Cuatro a seis años de práctica", "Nivel profesional"):
        assert level in system
    assert "especialmente problemático, que conviene trabajar aparte" in system, "the musicians' critical question"
    assert "ScoreLint" not in system


def test_gemini_reviews_with_the_review_schema():
    class Chat:
        def __init__(self):
            self.messages = None

        def invoke(self, messages):
            self.messages = messages
            return VALID
    chat, schemas = Chat(), []
    gemini = GeminiExplanationProvider("k", "m", chat_factory=lambda schema: schemas.append(schema.__name__) or chat)
    assert gemini.review_passage(FEATURES) == VALID
    assert schemas == ["PassageReview"]
    assert json.loads(chat.messages[1][1].split("\n", 1)[1]) == FEATURES
