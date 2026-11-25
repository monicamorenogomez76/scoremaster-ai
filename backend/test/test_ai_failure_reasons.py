"""The director is told why the AI did not answer (2026-11-25): its reason reaches the answer, not a bare «error»."""
import pytest

from backend.application.ai import FAILURES, ProviderFailure
from backend.application.explanations import failure_reason


@pytest.mark.parametrize("reason", ["timeout", "rate_limit", "model", "key", "overloaded", "error"])
def test_every_reason_reaches_the_answer(reason):
    assert reason in FAILURES
    assert failure_reason(ProviderFailure(reason)) == reason


def test_anything_else_is_an_error():
    assert failure_reason(ProviderFailure("the key is secret")) == "error"
    assert failure_reason(ValueError("timeout")) == "error"
