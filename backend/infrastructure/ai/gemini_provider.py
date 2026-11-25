"""Google Gemini through LangChain (step 21, chosen 2026-10-07: free tier).

LangChain stays behind the AI port: the domain only sees ExplanationProvider. Answers use structured
output with the same Pydantic schemas the server validates, temperature 0, a time limit and a single
retry; any failure becomes ProviderFailure (its reason) and the demo answers. The key
never reaches logs or the browser. LangChain is imported on first use: ~70 MB a keyless server skips."""
import logging
import os
import re
import time
from threading import Lock
from typing import Optional

from backend.application import ai_usage
from backend.application.ai import ProviderFailure, ProviderInfo
from backend.infrastructure.ai.prompts import (DIFFICULTY_PROMPT, INSTRUMENT_PROMPT, PASSAGE_REVIEW_PROMPT, REHEARSAL_PROMPT,
                                              MUSICAL_ANALYSIS_PROMPT, REPERTOIRE_QUESTION_PROMPT,
                                              REPERTOIRE_TOOL_CHOICE_PROMPT, SUBSTITUTES_PROMPT, TOOL_CHOICE_PROMPT,
                                              WORK_QUESTION_PROMPT, human_message, in_language)

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


# 2026-11-19: Google answered GoogleInvalidRequestError (400) to the musical analysis commentary: seven nested topics,
# each with bounded lists and a bounded text, are too complex for its structured output. For these schemas Gemini gets
# them without bounds, pattern or defaults and with every field required; the server still validates the bounds.
LEAN_SCHEMAS = {"MusicalAnalysisText"}
_BOUNDS = {"maxLength", "minLength", "maxItems", "minItems", "pattern", "default"}


def _lean(node):
    if isinstance(node, list):
        return [_lean(item) for item in node]
    if not isinstance(node, dict):
        return node
    lean = {key: _lean(value) for key, value in node.items() if key not in _BOUNDS}
    if isinstance(lean.get("properties"), dict):
        lean["required"] = list(lean["properties"])
    return lean


def answer_schema(schema):
    """What Gemini is asked to fill: the Pydantic schema, or its lean JSON schema for the complex ones."""
    return _lean(schema.model_json_schema()) if schema.__name__ in LEAN_SCHEMAS else schema


def _langchain_chat(api_key: str, model: str):
    def factory(schema):
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0,
                                      timeout=_timeout(), max_retries=1)
        # With the raw message too: its usage metadata gives the tokens of the call (M5, 2026-10-30).
        return chat.with_structured_output(answer_schema(schema), include_raw=True)
    return factory


def _langchain_tools(api_key: str, model: str):
    """M6 (2026-11-20): the chat with the read-only functions it may call, in LangChain's function format."""
    def factory(specs):
        from langchain_google_genai import ChatGoogleGenerativeAI
        chat = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0,
                                      timeout=_timeout(), max_retries=1)
        return chat.bind_tools(specs)
    return factory


# What each answer schema is for, in the usage panel.
PURPOSES = {"DifficultyExplanation": "difficulty", "RehearsalExplanation": "rehearsal", "PassageReview": "passage_review",
            "InstrumentProposals": "instrument_proposal", "SubstitutesExplanation": "substitutes",
            "MusicalAnalysisText": "musical_analysis", "WorkAnswer": "work_question"}


def _structured(answer):
    """The answer and its tokens: LangChain's include_raw gives {raw, parsed, parsing_error}; a plain answer has none."""
    if isinstance(answer, dict) and "raw" in answer and "parsed" in answer:
        usage = getattr(answer["raw"], "usage_metadata", None) or {}
        parsed = answer["parsed"]
        return (parsed if parsed is not None else {}), usage.get("input_tokens"), usage.get("output_tokens")
    return answer, None, None


# What Google's errors say, the first that matches. Whole words (2026-11-25): «generateContent» holds «rate», and a model
# that Google no longer had was told as a quota used up.
_REASONS = (
    ("timeout", re.compile(r"timeout|timed out|deadline|\b504\b")),
    ("rate_limit", re.compile(r"\b429\b|resource_?exhausted|quota|\brate[ _-]?limit")),
    ("key", re.compile(r"api[ _]key|\b401\b|\b403\b|permission_?denied|unauthenticated")),
    ("model", re.compile(r"\b404\b|not[ _]?found")),
    ("overloaded", re.compile(r"\b503\b|unavailable|overloaded")),
)


def _reason(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    text = (type(error).__name__ + " " + str(error)).lower()
    return next((reason for reason, said in _REASONS if said.search(text)), "error")


class GeminiExplanationProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, chat_factory=None, tools_factory=None):
        self.info = ProviderInfo("llm", "gemini", model)
        self._factory = chat_factory or _langchain_chat(api_key, model)
        self._tools_factory = tools_factory or _langchain_tools(api_key, model)
        self._chats, self._lock = {}, Lock()

    def _chat(self, schema):
        with self._lock:
            if schema not in self._chats:
                self._chats[schema] = self._factory(schema)
            return self._chats[schema]

    def _failed(self, error: Exception, prompt) -> ProviderFailure:
        reason = _reason(error)
        # Only the kind of failure: the exception text could carry request details.
        logger.warning("Gemini no respondió (%s, %s) con el prompt %s.", reason, type(error).__name__, prompt.version)
        if reason == "model":
            logger.warning("Google no encuentra el modelo %s: elige otro disponible con GEMINI_MODEL.", self.info.model)
        return ProviderFailure(reason)

    def choose_tools(self, question: str, specs: list[dict], language: str, scope: str = "work") -> list[dict]:
        """The calls Gemini makes to answer the question (M6), with their arguments; the caller runs only the known
        functions and ignores the arguments it does not understand."""
        prompt = REPERTOIRE_TOOL_CHOICE_PROMPT if scope == "repertoire" else TOOL_CHOICE_PROMPT
        functions = [{"type": "function", "function": {
            "name": spec["name"], "description": spec["description"],
            **({"parameters": spec["parameters"]} if "parameters" in spec else {})}} for spec in specs]
        with self._lock:
            key = ("tools", scope, language)
            if key not in self._chats:
                self._chats[key] = self._tools_factory(functions)
            chat = self._chats[key]
        started = time.monotonic()
        used = lambda outcome, tokens=(None, None): ai_usage.record(ai_usage.UsageEvent(
            scope + "_question_tools", self.info.model, prompt.version, "call", outcome,
            round((time.monotonic() - started) * 1000), *tokens))
        try:
            message = chat.invoke([("system", prompt.system), ("human", question)])
        except Exception as error:
            failure = self._failed(error, prompt)
            used(str(failure))
            raise failure from None
        usage = getattr(message, "usage_metadata", None) or {}
        used("ok", (usage.get("input_tokens"), usage.get("output_tokens")))
        return [{"name": call["name"], "args": call.get("args") or {}} for call in getattr(message, "tool_calls", None) or []
                if isinstance(call, dict) and "name" in call]

    def _ask(self, schema, prompt, evidence: dict, purpose: Optional[str] = None) -> dict:
        prompt = in_language(prompt, evidence.get("language", "es"))
        messages = [("system", prompt.system), ("human", human_message(evidence))]
        used = lambda outcome, started, tokens=(None, None): ai_usage.record(ai_usage.UsageEvent(
            purpose or PURPOSES.get(schema.__name__, schema.__name__), self.info.model, prompt.version, "call", outcome,
            round((time.monotonic() - started) * 1000), *tokens))
        started = time.monotonic()
        try:
            answer, *tokens = _structured(self._chat(schema).invoke(messages))
        except Exception as error:
            failure = self._failed(error, prompt)
            used(str(failure), started)
            raise failure from None
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

    def propose_instruments(self, evidence: dict) -> dict:
        from backend.application.instrument_proposals import InstrumentProposals
        return self._ask(InstrumentProposals, INSTRUMENT_PROMPT, evidence)

    def explain_substitutes(self, evidence: dict) -> dict:
        from backend.application.substitutes_explanation import SubstitutesExplanation
        return self._ask(SubstitutesExplanation, SUBSTITUTES_PROMPT, evidence)

    def answer_repertoire_question(self, evidence: dict) -> dict:
        from backend.application.work_questions import WorkAnswer
        return self._ask(WorkAnswer, REPERTOIRE_QUESTION_PROMPT, evidence, "repertoire_question")

    def answer_work_question(self, evidence: dict) -> dict:
        from backend.application.work_questions import WorkAnswer
        return self._ask(WorkAnswer, WORK_QUESTION_PROMPT, evidence)

    def explain_musical_analysis(self, evidence: dict) -> dict:
        from backend.application.musical_analysis_text import MusicalAnalysisText
        return self._ask(MusicalAnalysisText, MUSICAL_ANALYSIS_PROMPT, evidence)


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


_shared_analysis: Optional[GeminiExplanationProvider] = None


def shared_analysis_provider() -> Optional[GeminiExplanationProvider]:
    """The commentary of the musical analysis (2026-11-20) is the longest writing of the app: with the lite model it read as
    a list of data. It is asked for rarely and cached, so it uses the capable model unless GEMINI_ANALYSIS_MODEL says
    otherwise, whatever GEMINI_MODEL is."""
    global _shared_analysis
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("GEMINI_ANALYSIS_MODEL", "").strip() or DEFAULT_MODEL
    with _shared_lock:
        if _shared_analysis is None or _shared_analysis.info.model != model:
            _shared_analysis = GeminiExplanationProvider(key, model)
        return _shared_analysis


def reset_shared_provider() -> None:
    global _shared, _shared_review, _shared_analysis
    with _shared_lock:
        _shared = _shared_review = _shared_analysis = None
