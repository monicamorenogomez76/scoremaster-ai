"""Google Gemini through LangChain (step 21, chosen 2026-10-07: free tier).

LangChain stays behind the AI port: the domain only sees ExplanationProvider. Answers use structured
output with the same Pydantic schemas the server validates, temperature 0, a time limit and a single
retry; any failure becomes ProviderFailure (timeout, rate_limit, error) and the demo answers. The key
never reaches logs or the browser. LangChain is imported on first use: ~70 MB a keyless server skips."""
import logging
import os
import time
from threading import Lock
from typing import Optional

from backend.application import ai_usage
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.infrastructure.ai.prompts import DIFFICULTY_PROMPT, PASSAGE_REVIEW_PROMPT, REHEARSAL_PROMPT, human_message, in_language

# 2026-10-13: gemini-2.5-flash answered NotFound for a new key (Google keeps it only for accounts that
# used it before); 3.8 Flash is free on the standard tier.
DEFAULT_MODEL = "gemini-3.8-flash"
# 2026-10-13: gemini-3.8-flash always thinks first (thinking_level, which this LangChain version cannot
# lower); with Persis it took more than 25 s. A minute by default; GEMINI_TIMEOUT_SECONDS changes it.
TIMEOUT_SECONDS = 60


def _timeout() -> int:
    try:
        return max(5, int(os.environ.get("GEMINI_TIMEOUT_SECONDS", TIMEOUT_SECONDS)))
    except ValueError:
        return TIMEOUT_SECONDS
logger = logging.getLogger(__name__)


def _langchain_chat(api_key: str, model: str):
    def factory(schema):
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0,
                                      timeout=_timeout(), max_retries=1)
        # With the raw message too: its usage metadata gives the tokens of the call (M5, 2026-10-30).
        return chat.with_structured_output(schema, include_raw=True)
    return factory


# What each answer schema is for, in the usage panel.
PURPOSES = {"DifficultyExplanation": "difficulty", "RehearsalExplanation": "rehearsal", "PassageReview": "passage_review"}


def _structured(answer):
    """The answer and its tokens: LangChain's include_raw gives {raw, parsed, parsing_error}; a plain answer has none."""
    if isinstance(answer, dict) and "raw" in answer and "parsed" in answer:
        usage = getattr(answer["raw"], "usage_metadata", None) or {}
        parsed = answer["parsed"]
        return (parsed if parsed is not None else {}), usage.get("input_tokens"), usage.get("output_tokens")
    return answer, None, None


def _reason(error: Exception) -> str:
    text = (type(error).__name__ + " " + str(error)).lower()
    if isinstance(error, TimeoutError) or "timeout" in text or "timed out" in text or "deadline" in text:
        return "timeout"
    if "429" in text or "resource_exhausted" in text or "resourceexhausted" in text or "quota" in text or "rate" in text:
        return "rate_limit"
    return "error"


class GeminiExplanationProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, chat_factory=None):
        self.info = ProviderInfo("llm", "gemini", model)
        self._factory = chat_factory or _langchain_chat(api_key, model)
        self._chats, self._lock = {}, Lock()

    def _chat(self, schema):
        with self._lock:
            if schema not in self._chats:
                self._chats[schema] = self._factory(schema)
            return self._chats[schema]

    def _ask(self, schema, prompt, evidence: dict) -> dict:
        prompt = in_language(prompt, evidence.get("language", "es"))
        messages = [("system", prompt.system), ("human", human_message(evidence))]
        used = lambda outcome, started, tokens=(None, None): ai_usage.record(ai_usage.UsageEvent(
            PURPOSES.get(schema.__name__, schema.__name__), self.info.model, prompt.version, "call", outcome,
            round((time.monotonic() - started) * 1000), *tokens))
        started = time.monotonic()
        try:
            answer, *tokens = _structured(self._chat(schema).invoke(messages))
        except Exception as error:
            reason = _reason(error)
            used(reason, started)
            # Only the kind of failure: the exception text could carry request details.
            logger.warning("Gemini no respondió (%s, %s) con el prompt %s.", reason, type(error).__name__, prompt.version)
            if type(error).__name__ == "NotFound" or "not found" in str(error).lower():
                logger.warning("Google no encuentra el modelo %s: elige otro disponible con GEMINI_MODEL.", self.info.model)
            raise ProviderFailure(reason) from None
        used("ok", started, tokens)
        return answer.model_dump() if hasattr(answer, "model_dump") else answer

    def explain_difficulty(self, evidence: dict) -> dict:
        from backend.application.difficulty_explanation import DifficultyExplanation
        return self._ask(DifficultyExplanation, DIFFICULTY_PROMPT, evidence)

    def explain_rehearsal(self, evidence: dict) -> dict:
        from backend.application.rehearsal_explanation import RehearsalExplanation
        return self._ask(RehearsalExplanation, REHEARSAL_PROMPT, evidence)

    def review_passage(self, features: dict) -> dict:
        from backend.application.llm_review import PassageReview
        return self._ask(PassageReview, PASSAGE_REVIEW_PROMPT, features)


_shared: Optional[GeminiExplanationProvider] = None
_shared_lock = Lock()


def shared_provider() -> Optional[GeminiExplanationProvider]:
    """One client for the whole server when GEMINI_API_KEY is set; None otherwise (the demo answers)."""
    global _shared
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    with _shared_lock:
        if _shared is None:
            _shared = GeminiExplanationProvider(key, os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL)
        return _shared


_shared_review: Optional[GeminiExplanationProvider] = None


def shared_review_provider() -> Optional[GeminiExplanationProvider]:
    """The independent review of method B (step 22) may use its own model: GEMINI_REVIEW_MODEL (2026-10-13:
    gemini-3.5-flash-lite allows 500 requests a day against 20 of gemini-3.8-flash). Otherwise, the same."""
    global _shared_review
    model = os.environ.get("GEMINI_REVIEW_MODEL", "").strip()
    if not model:
        return shared_provider()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    with _shared_lock:
        if _shared_review is None or _shared_review.info.model != model:
            _shared_review = GeminiExplanationProvider(key, model)
        return _shared_review


def reset_shared_provider() -> None:
    global _shared, _shared_review
    with _shared_lock:
        _shared = _shared_review = None
