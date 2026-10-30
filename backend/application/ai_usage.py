"""What the AI layer spends (M5, 2026-10-30): every real call to the model, every answer read from the cache and every
answer discarded, for the administration's panel. Only counts, times and reasons: never a text nor who asked."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UsageEvent:
    purpose: str                    # difficulty, rehearsal or passage_review
    model: str
    prompt_version: str
    event: str                      # call, cache_hit or rejected
    outcome: str                    # ok, timeout, rate_limit, error or invalid
    latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    created_at: Optional[datetime] = None


class UsageRecorder(Protocol):
    def record(self, event: UsageEvent) -> None: ...


_recorder: Optional[UsageRecorder] = None


def use_recorder(recorder: Optional[UsageRecorder]) -> None:
    """Set at startup with the database; without one (tests, a server without PostgreSQL) nothing is recorded."""
    global _recorder
    _recorder = recorder


def record(event: UsageEvent) -> None:
    """Never stops an explanation: a failure to record is only logged."""
    if _recorder is None:
        return
    try:
        _recorder.record(event)
    except Exception:
        logger.warning("No se pudo registrar el uso de la IA.", exc_info=True)
