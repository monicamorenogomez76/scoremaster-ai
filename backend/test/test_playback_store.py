"""Prepared works survive a restart, and a slow preparation never keeps a request open for minutes
(2026-10-07: on Render's free plan reading Persis took about three minutes; a passage asked for while
it was being read went past the browser's wait, and the server forgot it every time it slept)."""
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_playback_store
from backend.app.main import app
from backend.parsers import playback
from backend.parsers.playback import TIMELINE_VERSION, build_playback, prepare_playback

SCORES = Path(__file__).resolve().parents[2] / "test-scores"
CONTENT = (SCORES / "high_density.musicxml").read_bytes()


class MemoryStore:
    def __init__(self):
        self.rows, self.saved = {}, 0

    def load(self, key, version):
        row = self.rows.get(key)
        return row[1] if row and row[0] == version else None

    def save(self, key, version, data):
        self.rows[key] = (version, data)
        self.saved += 1


class BrokenStore:
    def load(self, key, version):
        raise RuntimeError("database down")

    def save(self, key, version, data):
        raise RuntimeError("database down")


def _count_parses(monkeypatch):
    calls = []
    original = playback.converter.parse
    monkeypatch.setattr(playback.converter, "parse", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs))
    return calls


def test_a_prepared_work_is_kept_and_read_back_after_a_restart_without_music21(monkeypatch):
    playback.clear_timelines()
    fresh = build_playback(CONTENT, "", 0, 999999)
    solo = build_playback(CONTENT, "Clarinet", 1, 1)
    playback.clear_timelines()
    store = MemoryStore()
    prepare_playback(CONTENT, store)
    assert store.saved == 1
    playback.clear_timelines()                      # the server slept or was deployed again
    calls = _count_parses(monkeypatch)
    assert build_playback(CONTENT, "", 0, 999999, store) == fresh
    assert build_playback(CONTENT, "Clarinet", 1, 1, store) == solo
    assert calls == [], "read back from the store, not from music21"


def test_a_timeline_of_an_older_version_is_prepared_again(monkeypatch):
    playback.clear_timelines()
    store = MemoryStore()
    store.save(playback.timeline_key(CONTENT), "playback-timeline-v0", b"old format")
    calls = _count_parses(monkeypatch)
    build_playback(CONTENT, "Clarinet", 1, 1, store)
    assert calls == [1]
    assert store.rows[playback.timeline_key(CONTENT)][0] == TIMELINE_VERSION


def test_playback_still_works_when_the_store_fails():
    playback.clear_timelines()
    expected = build_playback(CONTENT, "Clarinet", 1, 1)
    playback.clear_timelines()
    assert build_playback(CONTENT, "Clarinet", 1, 1, BrokenStore()) == expected


@pytest.fixture
def slow_reading(monkeypatch):
    """Reading any work waits until the test releases it, as on a slow server."""
    release = threading.Event()
    original = playback._read_timeline
    monkeypatch.setattr(playback, "_read_timeline", lambda source: release.wait(10) and original(source))
    monkeypatch.setattr(playback, "WAIT_SECONDS", 0.2)
    playback.clear_timelines()
    yield release
    release.set()
    playback.wait_for_preparations()


def _ask(client, content=CONTENT):
    return client.post("/playback", files={"file": ("obra.musicxml", content)},
                       data={"instrument": "Clarinet", "first_measure": 1, "last_measure": 1})


def test_a_slow_work_answers_at_once_that_it_is_being_prepared(slow_reading):
    client = TestClient(app)
    response = _ask(client)
    assert response.status_code == 202
    key = response.json()["preparing"]
    assert key == playback.timeline_key(CONTENT)
    assert client.get("/playback/preparations/" + key).json() == {"status": "preparing"}
    assert _ask(client).status_code == 202, "asking again does not start a second reading"

    slow_reading.set()
    playback.wait_for_preparations()
    assert client.get("/playback/preparations/" + key).json() == {"status": "ready"}
    ready = _ask(client)
    assert ready.status_code == 200 and ready.json()["instrument"] == "Clarinet"


def test_a_failed_preparation_is_reported(monkeypatch):
    monkeypatch.setattr(playback, "WAIT_SECONDS", 0.2)
    playback.clear_timelines()
    client = TestClient(app)
    response = _ask(client, b"<not-a-score/>")
    assert response.status_code == 400
    assert response.json()["detail"] == "La partitura no es MusicXML válido."
    key = playback.timeline_key(b"<not-a-score/>")
    assert client.get("/playback/preparations/" + key).json() == {"status": "failed"}


def test_a_preparation_the_server_does_not_know_is_reported_as_unknown():
    """After a restart the browser sends the work again to start its preparation."""
    playback.clear_timelines()
    client = TestClient(app)
    assert client.get("/playback/preparations/" + "0" * 64).json() == {"status": "unknown"}
    assert client.get("/playback/preparations/not-a-key").status_code == 422


def test_the_endpoint_keeps_prepared_works_in_the_store():
    playback.clear_timelines()
    store = MemoryStore()
    app.dependency_overrides[get_playback_store] = lambda: store
    try:
        assert _ask(TestClient(app)).status_code == 200
    finally:
        app.dependency_overrides.pop(get_playback_store)
    assert store.saved == 1


# A large work without its audio (2026-11-25): music21 took 573 MB of the server, Render has 512 and restarted it (502).
def large_work():
    return CONTENT.replace(b"</score-partwise>", b"<!--" + b"x" * playback.LARGE_SOURCE + b"--></score-partwise>")


@pytest.fixture
def outside(monkeypatch):
    """The reader of large works outside the server, counted."""
    read = []

    def reader(content):
        read.append(content)
        return playback.encode_timeline(content)
    playback.clear_timelines()
    playback.read_large_works_with(reader)
    yield read
    playback.read_large_works_with(None)
    playback.clear_timelines()


def test_a_large_work_is_read_outside_the_server_and_kept(outside):
    store, content = MemoryStore(), large_work()
    assert playback.build_playback(content, "", 0, 999999, store)["tracks"]
    assert outside == [content]
    assert store.load(playback.timeline_key(content), playback.TIMELINE_VERSION)
    playback.build_playback(content, "", 0, 999999, store)
    assert len(outside) == 1


def test_a_small_work_is_read_in_the_server(outside):
    assert playback.build_playback(CONTENT, "", 0, 999999, MemoryStore())["tracks"]
    assert not outside


def test_a_large_work_that_does_not_fit_is_a_failed_preparation_not_a_dead_server(outside):
    def killed(content):
        raise playback.WorkTooLarge
    playback.read_large_works_with(killed)
    with pytest.raises(playback.WorkTooLarge):
        playback.build_playback(large_work(), "", 0, 999999, MemoryStore())
    assert playback.preparation_status(playback.timeline_key(large_work())) == "failed"


def test_the_endpoint_says_that_the_work_does_not_fit(outside):
    def killed(content):
        raise playback.WorkTooLarge
    playback.read_large_works_with(killed)
    response = _ask(TestClient(app), large_work())
    assert response.status_code == 400
    assert response.json()["detail"] == "La obra es demasiado grande para preparar su audio en este servidor."


def test_the_own_process_of_a_large_work_gives_its_timeline_or_says_it_does_not_fit(monkeypatch):
    from backend.app import stored_scores
    assert playback.timeline_has_parts(stored_scores.timeline_in_own_process(CONTENT))
    monkeypatch.setattr(stored_scores.sys, "executable", "/bin/false")
    with pytest.raises(playback.WorkTooLarge):
        stored_scores.timeline_in_own_process(CONTENT)
