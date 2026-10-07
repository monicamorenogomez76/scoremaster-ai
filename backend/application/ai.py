"""Port of the AI layer (step 20). ScoreLint stays the source of musical facts: a provider only writes
explanations from evidence it is given, and its answers are validated before being shown. The domain
never depends on a concrete provider; the demo provider answers without an API key."""
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ProviderInfo:
    kind: str                  # "demo" (rules, never presented as AI) or "llm"
    name: str                  # "demo", "gemini", "fake"…
    model: Optional[str] = None


class ProviderFailure(Exception):
    """A provider that did not answer: timeout, rate_limit or error (the reason is the message)."""


class ExplanationProvider(Protocol):
    info: ProviderInfo

    def explain_difficulty(self, evidence: dict) -> dict:
        """The raw answer to the difficulty explanation schema; validated by the caller."""
