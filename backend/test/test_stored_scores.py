"""Each work is parsed once and its musical model kept (2026-10-07: every rehearsal or concert
proposal read every work of the programme with music21 again: minutes with Persis on Render)."""
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app import stored_scores
from backend.app.stored_scores import parsed_work, prepare_missing_works, stored_score
from backend.application.library import WorkUpload
from backend.parsers import playback
from backend.parsers.score_codec import SCORE_VERSION
from backend.test.library_fakes import InMemoryLibrary
from backend.test.test_playback_store import BrokenStore, MemoryStore

SCORES = Path(__file__).resolve().parents[2] / "test-scores"
CONTENT = (SCORES / "high_density.musicxml").read_bytes()


@pytest.fixture
def parses(monkeypatch):
    stored_scores.clear_parsed_works()
    calls = []
    original = stored_scores.parse_musicxml
    monkeypatch.setattr(stored_scores, "parse_musicxml", lambda *args: calls.append(1) or original(*args))
    return calls


def test_a_work_is_parsed_once(parses):
    first = parsed_work(CONTENT)
    assert parsed_work(CONTENT) == first
    assert parses == [1]


def test_a_parsed_work_is_read_back_after_a_restart(parses):
    store = MemoryStore()
    first = parsed_work(CONTENT, store)
    stored_scores.clear_parsed_works()
    assert parsed_work(CONTENT, store) == first
    assert parses == [1]
    assert next(iter(store.rows.values()))[0] == SCORE_VERSION


def test_a_broken_store_does_not_stop_the_analysis(parses):
    assert parsed_work(CONTENT, BrokenStore()).parts


def test_the_instruments_confirmed_by_each_user_are_applied_on_top(parses, monkeypatch):
    library, user = InMemoryLibrary(), uuid4()
    work = library.store_work(user, WorkUpload("Obra", None, "obra.musicxml", CONTENT, "x"))
    name = parsed_work(CONTENT).parts[0].name
    monkeypatch.setattr(library, "latest_analysis", lambda *args: type("A", (), {"configuration": {
        "instrument_overrides": {name: "clarinet.bb"}}})())
    _, confirmed = stored_score(library, user, work.id)
    assert confirmed.parts[0].metadata.confirmed_id == "clarinet.bb"
    assert parsed_work(CONTENT).parts[0].metadata.confirmed_id is None, "the kept model is not changed"
    assert parses == [1]


def test_works_uploaded_before_are_prepared_when_the_server_starts(parses):
    class Stores(MemoryStore):
        def __init__(self, sources):
            super().__init__()
            self.sources = sources

        def missing_sources(self, version):
            return iter(self.sources)
    scores, timelines = Stores([CONTENT]), Stores([CONTENT])
    playback.clear_timelines()
    prepare_missing_works(scores, timelines)
    assert scores.saved == 1 and timelines.saved == 1
    assert parses == [1]


def test_a_work_parsed_without_a_store_is_kept_when_a_store_is_given(parses):
    parsed_work(CONTENT)
    store = MemoryStore()
    parsed_work(CONTENT, store)
    assert store.saved == 1 and parses == [1]
    parsed_work(CONTENT, store)
    assert store.saved == 1, "saved once"
