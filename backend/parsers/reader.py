"""One music21 reading at a time: on Render's free plan (512 MB) two band scores parsed at once do
not fit in memory (analysis ~450 MB, playback ~330 MB at their peak, 2026-10-07)."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
import gc
from threading import Lock
import time
from typing import Optional

reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix='music21')
# What takes hundreds of MB outside that thread takes turns (2026-11-06): the works of the startup, one by one, and a reading
# of a PDF being received. Never held by the reader thread, so read() may be called while holding it.
ONE_READING = Lock()
# The startup leaves its turn to a reading that asked, which comes back within minutes: the reader's waits, in omr/worker.py.
READING_FIRST_SECONDS = 360   # more than its longest wait
_reading_asked: Optional[float] = None
_reading_received = False


class StartupStopped(Exception):
    """A reading was received: what it leaves in memory and music21 do not fit, and the next start goes on."""


def read(function, *args):
    """Runs function in the reader thread and waits for it. Never call it from the reader thread."""
    return reader.submit(function, *args).result()


def release_memory() -> None:
    """Gives back what music21 and a large XML tree left: glibc keeps it otherwise, and the next turn starts higher."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass   # not Linux


def ask_for_turn() -> bool:
    """The turn for a reading, without waiting: refused, it is the next when it comes back."""
    global _reading_asked, _reading_received
    if ONE_READING.acquire(blocking=False):
        _reading_asked, _reading_received = None, True
        return True
    _reading_asked = time.monotonic()
    return False


def end_turn() -> None:
    ONE_READING.release()
    release_memory()


@contextmanager
def startup_turn():
    while _reading_asked is not None and time.monotonic() - _reading_asked < READING_FIRST_SECONDS:
        time.sleep(1)
    with ONE_READING:
        if _reading_received:
            raise StartupStopped
        yield
    release_memory()
