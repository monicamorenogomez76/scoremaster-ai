"""Google Gemini through LangChain (step 21, author's choice 2026-10-07: free tier).

LangChain stays behind the AI port: the domain only sees ExplanationProvider. Answers use structured
output with the same Pydantic schemas the server validates, temperature 0, a time limit and a single
retry; any failure becomes ProviderFailure (timeout, rate_limit, error) and the demo answers. The key
never reaches logs or the browser. LangChain is imported on first use: ~70 MB a keyless server skips."""
import logging
import os
from threading import Lock
from typing import Optional

from backend.application.ai import ProviderFailure, ProviderInfo
from backend.infrastructure.ai.prompts import DIFFICULTY_PROMPT, REHEARSAL_PROMPT, human_message

DEFAULT_MODEL = "gemini-2.5-flash"
TIMEOUT_SECONDS = 25
logger = logging.getLogger(__name__)


def _langchain_chat(api_key: str, model: str):
    def factory(schema):
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0,
                                      timeout=TIMEOUT_SECONDS, max_retries=1)
        return chat.with_structured_output(schema)
    return factory


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
        messages = [("system", prompt.system), ("human", human_message(evidence))]
        try:
            answer = self._chat(schema).invoke(messages)
        except Exception as error:
            reason = _reason(error)
            # Only the kind of failure: the exception text could carry request details.
            logger.warning("Gemini no respondió (%s, %s) con el prompt %s.", reason, type(error).__name__, prompt.version)
            raise ProviderFailure(reason) from None
        return answer.model_dump() if hasattr(answer, "model_dump") else answer

    def explain_difficulty(self, evidence: dict) -> dict:
        from backend.application.difficulty_explanation import DifficultyExplanation
        return self._ask(DifficultyExplanation, DIFFICULTY_PROMPT, evidence)

    def explain_rehearsal(self, evidence: dict) -> dict:
        from backend.application.rehearsal_explanation import RehearsalExplanation
        return self._ask(RehearsalExplanation, REHEARSAL_PROMPT, evidence)


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


def reset_shared_provider() -> None:
    global _shared
    with _shared_lock:
        _shared = None
