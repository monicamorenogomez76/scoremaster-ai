"""Independent review of a passage by the LLM (step 22, method B of docs/EVALUATION_AND_FEEDBACK.md).

The LLM rates the passage from its measurements and notes (backend/analyzers/passage_features.py) with
the same rubric and critical question as the musicians, never seeing ScoreLint's prediction. There is no
demo: a rule-based stand-in would be one more heuristic. A failure is reported, never replaced."""
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from backend.application import ai_usage
from backend.application.explanations import InvalidExplanation

PROMPT_VERSION = "passage-review-v2"
FACTORS = ("rhythm", "tempo", "range", "register", "intervals", "endurance", "articulation", "reading", "other")


class InvalidReview(InvalidExplanation):
    """The answer is outside the rubric or the schema."""


class NotAvailable(Exception):
    """No real AI provider is configured: the independent review cannot run."""


class PassageReview(BaseModel):
    grade: int = Field(ge=1, le=6)
    critical: bool
    confidence: float = Field(ge=0, le=1)
    main_factors: list[Literal["rhythm", "tempo", "range", "register", "intervals", "endurance", "articulation",
                               "reading", "other"]] = Field(min_length=1, max_length=3)
    reason: str = Field(min_length=1, max_length=400)


def validate_review(answer) -> PassageReview:
    try:
        return PassageReview.model_validate(answer)
    except ValidationError as error:
        fields = sorted({str(item["loc"][0]) for item in error.errors() if item.get("loc")})
        raise InvalidReview("Valoración fuera de la rúbrica: " + ", ".join(fields or ["?"])) from None


def review_passage(features: dict, provider) -> dict:
    """The review of one passage with who wrote it; raises ProviderFailure, InvalidReview or NotAvailable."""
    if provider.info.kind != "llm" or not hasattr(provider, "review_passage"):
        raise NotAvailable("La valoración independiente necesita un proveedor de IA real (GEMINI_API_KEY).")
    try:
        review = validate_review(provider.review_passage(features))
    except InvalidReview:
        ai_usage.record(ai_usage.UsageEvent("passage_review", provider.info.model or provider.info.name, PROMPT_VERSION,
                                            "rejected", "invalid"))
        raise
    return {**review.model_dump(), "provider": provider.info.name, "model": provider.info.model,
            "prompt_version": PROMPT_VERSION, "features_version": features["version"]}
