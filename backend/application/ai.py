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


# Why a provider did not answer: too slow, its quota used up, a model it does not have, a key it refuses, too busy, or
# anything else.
FAILURES = ("timeout", "rate_limit", "model", "key", "overloaded", "error")


class ProviderFailure(Exception):
    """A provider that did not answer: the reason, one of FAILURES, is the message."""


class ExplanationProvider(Protocol):
    info: ProviderInfo

    def explain_difficulty(self, evidence: dict) -> dict:
        """The raw answer to the difficulty explanation schema; validated by the caller."""

    def explain_rehearsal(self, evidence: dict) -> dict:
        """The raw answer to the rehearsal explanation schema; validated by the caller."""
