"""One music21 reading at a time: on Render's free plan (512 MB) two band scores parsed at once do
not fit in memory (analysis ~450 MB, playback ~330 MB at their peak, 2026-10-07)."""
from concurrent.futures import ThreadPoolExecutor

reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix='music21')


def read(function, *args):
    """Runs function in the reader thread and waits for it. Never call it from the reader thread."""
    return reader.submit(function, *args).result()
