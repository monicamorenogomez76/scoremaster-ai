"""AI usage panel for the administration (M5, 2026-10-30). Every real call to the model is recorded with its purpose,
model, prompt version, outcome, latency and tokens; every answer read from the cache and every answer discarded too.
Nothing written by a user, nor who asked, is kept: only counts, times and reasons."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.application import ai_usage
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.application.ai_usage import UsageEvent
from backend.application.explanations import run_explanation
from backend.app.dependencies import get_ai_usage_repository
from backend.app.main import app
from backend.infrastructure.ai.gemini_provider import GeminiExplanationProvider
from backend.infrastructure.ai_usage_repository import PostgresAiUsageRepository
from backend.test.test_difficulty_explanation import result, valid_answer  # noqa: F401 (fixture)
from backend.application.difficulty_explanation import difficulty_evidence, explain_difficulty
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider


class Recorded:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


@pytest.fixture
def recorded():
    recorder = Recorded()
    ai_usage.use_recorder(recorder)
    yield recorder
    ai_usage.use_recorder(None)


def structured(answer, input_tokens=1200, output_tokens=300):
    """What LangChain's structured output returns with include_raw: the message with its usage and the answer."""
    return {"raw": SimpleNamespace(usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens}),
            "parsed": answer, "parsing_error": None}


def test_a_call_to_gemini_is_recorded_with_its_tokens_latency_and_prompt(result, recorded):
    evidence = difficulty_evidence(result)

    class Chat:
        def invoke(self, messages):
            return structured(valid_answer(evidence))

    provider = GeminiExplanationProvider("key", "gemini-test", chat_factory=lambda schema: Chat())
    shown = explain_difficulty(result, provider, DemoExplanationProvider())
    assert shown["mode"] == "llm"
    [event] = recorded.events
    assert (event.purpose, event.model, event.prompt_version, event.event, event.outcome) == \
        ("difficulty", "gemini-test", "difficulty-explanation-v4", "call", "ok")
    assert (event.input_tokens, event.output_tokens) == (1200, 300) and event.latency_ms >= 0


def test_a_failed_call_is_recorded_with_its_reason(result, recorded):
    class Chat:
        def invoke(self, messages):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    provider = GeminiExplanationProvider("key", "gemini-test", chat_factory=lambda schema: Chat())
    assert explain_difficulty(result, provider, DemoExplanationProvider())["fallback_reason"] == "rate_limit"
    assert [(event.event, event.outcome, event.input_tokens) for event in recorded.events] == [("call", "rate_limit", None)]


class Fake:
    info = ProviderInfo("llm", "fake", "fake-model")

    def __init__(self, answer):
        self.answer = answer

    def explain_difficulty(self, evidence):
        return self.answer


class Cache:
    def __init__(self):
        self.kept = {}

    def load(self, key):
        return self.kept.get(key)

    def save(self, key, value):
        self.kept[key] = value


def test_cache_hits_and_discarded_answers_are_recorded(result, recorded):
    evidence = difficulty_evidence(result)
    validate = __import__("backend.application.difficulty_explanation", fromlist=["x"]).validate_explanation
    ask = lambda who, data: who.explain_difficulty(data)
    cache = Cache()
    run_explanation(evidence, ask, validate, Fake(valid_answer(evidence)), DemoExplanationProvider(), "v", cache=cache, purpose="difficulty")
    run_explanation(evidence, ask, validate, Fake(valid_answer(evidence)), DemoExplanationProvider(), "v", cache=cache, purpose="difficulty")
    wrong = {**valid_answer(evidence), "factors": [{"dimension": "general", "text": "x", "passages": ["P99"]}]}
    run_explanation(evidence, ask, validate, Fake(wrong), DemoExplanationProvider(), "v", purpose="difficulty")
    assert [(event.event, event.outcome, event.model) for event in recorded.events] == \
        [("cache_hit", "ok", "fake-model"), ("rejected", "invalid", "fake-model")]


def test_the_demo_is_never_recorded(result, recorded):
    explain_difficulty(result, DemoExplanationProvider(), DemoExplanationProvider())
    assert recorded.events == []


def test_the_table_keeps_no_text_and_no_account(postgres_engine):
    columns = {column["name"] for column in inspect(postgres_engine).get_columns("ai_usage")}
    assert columns == {"id", "created_at", "purpose", "model", "prompt_version", "event", "outcome", "latency_ms",
                       "input_tokens", "output_tokens"}


def _event(**fields):
    base = dict(purpose="difficulty", model="gemini-3.8-flash", prompt_version="difficulty-explanation-v4", event="call",
                outcome="ok", latency_ms=1000, input_tokens=1000, output_tokens=200)
    return UsageEvent(**{**base, **fields})


def test_the_summary_counts_calls_tokens_cost_latency_cache_and_rejections(postgres_engine, monkeypatch):
    monkeypatch.setenv("GEMINI_PRICE_INPUT_PER_MTOK", "0.30")
    monkeypatch.setenv("GEMINI_PRICE_OUTPUT_PER_MTOK", "2.50")
    usage = PostgresAiUsageRepository(postgres_engine)
    for latency in (1000, 2000, 3000, 4000, 10000):
        usage.record(_event(latency_ms=latency))
    usage.record(_event(outcome="timeout", latency_ms=60000, input_tokens=None, output_tokens=None))
    usage.record(_event(model="gemini-3.5-flash-lite", purpose="passage_review", prompt_version="passage-review-v2"))
    usage.record(_event(event="cache_hit", latency_ms=None, input_tokens=None, output_tokens=None))
    usage.record(_event(event="rejected", outcome="invalid", latency_ms=None, input_tokens=None, output_tokens=None))
    usage.record(_event(created_at=datetime.now(timezone.utc) - timedelta(days=40)))

    summary = usage.summary(days=30)
    flash = next(item for item in summary["models"] if item["model"] == "gemini-3.8-flash")
    assert (flash["calls"], flash["failed"], flash["input_tokens"], flash["output_tokens"]) == (6, 1, 5000, 1000)
    assert flash["latency_ms"] == {"average": 13333, "p95": 60000}
    assert flash["estimated_cost"] == pytest.approx(5000 * 0.30 / 1e6 + 1000 * 2.50 / 1e6)
    assert summary["failures"] == {"timeout": 1}
    assert summary["cache_hits"] == 1 and summary["rejected"] == {"invalid": 1}
    assert {item["purpose"]: item["calls"] for item in summary["purposes"]} == {"difficulty": 6, "passage_review": 1}
    assert summary["days"] == 30 and summary["priced"] is True


@pytest.mark.real_auth
def test_only_the_administration_sees_the_panel(postgres_engine, monkeypatch):
    from backend.app.dependencies import get_account_repository
    from backend.infrastructure.account_repository import PostgresAccountRepository
    monkeypatch.setenv("ADMIN_EMAILS", "admin@banda.org")
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    app.dependency_overrides[get_ai_usage_repository] = lambda: PostgresAiUsageRepository(postgres_engine)
    try:
        admin, other = TestClient(app), TestClient(app)
        admin.post("/auth/register", json={"email": "admin@banda.org", "password": "una contraseña larga"})
        other.post("/auth/register", json={"email": "musico@banda.org", "password": "una contraseña larga"})
        assert other.get("/admin/ai-usage").status_code == 403
        response = admin.get("/admin/ai-usage?days=7")
        assert response.status_code == 200 and response.json()["days"] == 7
        assert admin.get("/admin/ai-usage?days=0").status_code == 422
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
