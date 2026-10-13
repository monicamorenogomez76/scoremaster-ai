"""Running the independent review over a campaign in the background (step 22).

One campaign at a time, a pause between requests to stay within the free quota, one wait and retry
when the provider says the quota is spent (then a pause until the next run), and failures counted rather
than stored: a passage that
failed is asked again the next time. Nothing is lost on a restart: the stored reviews say what is done."""
import logging
import os
import time
from dataclasses import dataclass, field
from threading import Lock, Thread
from typing import Callable, Optional

from backend.application.ai import ProviderFailure
from backend.application.llm_review import InvalidReview

logger = logging.getLogger(__name__)


def _pause() -> float:
    """Seconds between requests: GEMINI_REQUESTS_PER_MINUTE (5 by default, well inside the free tier)."""
    try:
        per_minute = float(os.environ.get("GEMINI_REQUESTS_PER_MINUTE", "5"))
    except ValueError:
        per_minute = 5
    return 60.0 / per_minute if per_minute > 0 else 0.0


PAUSE_SECONDS: Optional[float] = None      # tests set 0
RATE_LIMIT_WAIT = 60.0


@dataclass
class Job:
    state: str = "running"
    asked: int = 0
    failed: int = 0
    last_error: Optional[str] = None
    thread: Optional[Thread] = field(default=None, repr=False)


_jobs: dict = {}
_lock = Lock()
_one_at_a_time = Lock()


def job(campaign_id) -> Optional[Job]:
    with _lock:
        return _jobs.get(campaign_id)


def _run(current: Job, todo: list, review: Callable, save: Callable) -> None:
    pause = _pause() if PAUSE_SECONDS is None else PAUSE_SECONDS
    with _one_at_a_time:
        for index, passage in enumerate(todo):
            if current.state == "paused":
                break
            if index and pause:
                time.sleep(pause)
            for attempt in (1, 2):
                try:
                    reviewed, features = review(passage)
                    save(passage, reviewed, features)
                    current.asked += 1
                    break
                except ProviderFailure as failure:
                    if str(failure) == "rate_limit" and attempt == 1:
                        time.sleep(RATE_LIMIT_WAIT if pause else 0)
                        continue
                    if str(failure) == "rate_limit":
                        # The quota is spent: asking the rest would only fail. The next run continues here.
                        current.state, current.last_error = "paused", "rate_limit"
                        break
                    current.failed, current.last_error = current.failed + 1, str(failure)
                except InvalidReview:
                    current.failed, current.last_error = current.failed + 1, "invalid"
                except Exception as error:
                    logger.warning("No se pudo valorar un pasaje con IA (%s).", type(error).__name__)
                    current.failed, current.last_error = current.failed + 1, "error"
                break
    if current.state == "running":
        current.state = "done"


def start(campaign_id, todo: list, review: Callable, save: Callable) -> Job:
    """Starts the review of the passages still to do, unless one is already running for this campaign."""
    with _lock:
        running = _jobs.get(campaign_id)
        if running is not None and running.state == "running":
            return running
        current = Job()
        current.thread = Thread(target=_run, args=(current, todo, review, save), daemon=True, name="llm-review")
        _jobs[campaign_id] = current
    current.thread.start()
    return current


def wait_for_jobs() -> None:
    with _lock:
        threads = [item.thread for item in _jobs.values() if item.thread is not None]
    for thread in threads:
        thread.join()
