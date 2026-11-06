from hashlib import sha256
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
    order = []
    prepare_missing_works(scores, timelines, after_models=lambda: order.append(("analyses", timelines.saved)))
    assert scores.saved == 1 and timelines.saved == 1
    assert parses == [1]
    # difficulty-v2 (2026-10-14): outdated analyses are made again once the models are read, before the
    # audio, which on Render's free plan can take many minutes for every work.
    assert order == [("analyses", 0)]


def test_a_work_parsed_without_a_store_is_kept_when_a_store_is_given(parses):
    parsed_work(CONTENT)
    store = MemoryStore()
    parsed_work(CONTENT, store)
    assert store.saved == 1 and parses == [1]
    parsed_work(CONTENT, store)
    assert store.saved == 1, "saved once"


def test_the_works_of_the_startup_take_turns_with_a_reading_of_a_pdf(monkeypatch):
    # Render's 512 MB (2026-11-06): music21 over the works of the startup and a reading of 12 MB being received do not fit.
    from backend.app import stored_scores
    from backend.parsers.reader import ONE_READING
    held = []

    class Missing:
        def missing_sources(self, version):
            return iter([b"one", b"two"])

    monkeypatch.setattr(stored_scores, "parsed_work", lambda source, store: held.append(("model", ONE_READING.locked())))
    monkeypatch.setattr(stored_scores, "prepare_playback", lambda source, store: held.append(("audio", ONE_READING.locked())))
    assert not ONE_READING.locked()
    prepare_missing_works(Missing(), Missing())
    assert held == [("model", True), ("model", True), ("audio", True), ("audio", True)]
    assert not ONE_READING.locked(), "between two works, the reading goes first"


def test_a_reading_that_asked_goes_before_the_next_work_of_the_startup(monkeypatch):
    from backend.parsers import reader
    waits = []
    monkeypatch.setattr(reader.time, "sleep", waits.append)
    now = [1000.0]
    monkeypatch.setattr(reader.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(reader, "_reading_asked", None)
    assert reader.ONE_READING.acquire(blocking=False)
    assert not reader.ask_for_turn(), "a work of the startup is being read"
    reader.ONE_READING.release()

    def time_passes(seconds):
        waits.append(seconds)
        now[0] += reader.READING_FIRST_SECONDS
    monkeypatch.setattr(reader.time, "sleep", time_passes)
    with reader.startup_turn():
        assert reader.ONE_READING.locked()
    assert waits, "it waited for the reading, which may never come back"
    assert not reader.ONE_READING.locked()


def test_a_work_of_the_startup_can_be_prepared_by_other_processes(parses):
    # Render's 512 MB (2026-11-06): what music21 leaves in the server does not leave room to receive a reading.
    class Stores(MemoryStore):
        def __init__(self, sources):
            super().__init__()
            self.sources = sources

        def missing_sources(self, version):
            return iter(self.sources)
    prepared = []
    scores, timelines = Stores([CONTENT]), Stores([CONTENT])
    prepare_missing_works(scores, timelines, read_work=lambda kind, source: prepared.append((kind, source)))
    assert prepared == [("score", CONTENT), ("playback", CONTENT)], "each with its own process: the peak of each is lower"
    assert not parses and scores.saved == 0, "the server itself read nothing"


@pytest.mark.parametrize("kind", ["score", "playback"])
def test_another_process_prepares_the_work_and_the_server_keeps_it(monkeypatch, kind):
    from backend.app import stored_scores
    from backend.parsers.playback import TIMELINE_VERSION
    from backend.parsers.score_codec import SCORE_VERSION, decode_score

    def refuse(*_):
        raise AssertionError("the server read it with music21")
    monkeypatch.setattr(stored_scores, "parse_musicxml", refuse)
    store = MemoryStore()
    source = (Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml").read_bytes()
    stored_scores.prepare_in_own_process(kind, source, store)
    key = sha256(source).hexdigest()
    if kind == "score":
        assert decode_score(store.load(key, SCORE_VERSION)).parts
    else:
        assert store.load(key, TIMELINE_VERSION)


def test_the_process_of_a_work_connects_with_the_url_neon_gives(monkeypatch):
    """Neon's URL names no driver; SQLAlchemy would then look for psycopg2, which is not installed."""
    from backend.app import stored_scores
    from backend.parsers.score_codec import SCORE_VERSION
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:1/nothing?sslmode=disable")
    store = MemoryStore()
    source = (Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml").read_bytes()
    stored_scores.prepare_in_own_process("score", source, store)
    assert store.load(sha256(source).hexdigest(), SCORE_VERSION), "without its catalog, the work is still prepared"


def test_a_process_that_dies_stops_nothing(monkeypatch, caplog):
    from backend.app import stored_scores
    store = MemoryStore()
    monkeypatch.setattr(stored_scores.sys, "executable", "/bin/false")
    stored_scores.prepare_in_own_process("score", b"<score-partwise/>", store)
    assert store.saved == 0
    assert "No se pudo preparar una obra" in caplog.text


def test_a_process_that_fails_says_why_without_its_message(monkeypatch, caplog):
    """The message of an error may carry the address of the database: only the name of the error goes to the log."""
    from backend.app import stored_scores
    monkeypatch.setattr(stored_scores.subprocess, "run", lambda *_, **__: (_ for _ in ()).throw(
        stored_scores.subprocess.CalledProcessError(1, "child", stderr=b"Traceback\nValueError: postgresql://secret\n")))
    stored_scores.prepare_in_own_process("score", b"<score-partwise/>", MemoryStore())
    assert "ValueError" in caplog.text and "salida 1" in caplog.text
    assert "secret" not in caplog.text


def test_the_process_of_a_work_is_the_first_to_go_when_memory_runs_out(tmp_path):
    from backend.app.prepare_child import die_first
    target = tmp_path / "oom_score_adj"
    target.write_text("0")
    die_first(target)
    assert target.read_text() == "1000"
    die_first(tmp_path / "not" / "linux")


def test_a_kept_model_is_found_and_a_missing_one_is_not_read(parses):
    from backend.app.stored_scores import kept_work
    store = MemoryStore()
    assert kept_work(CONTENT, store) is None
    assert not parses, "this process may have no room for music21"
    parsed_work(CONTENT, store)
    assert kept_work(CONTENT, store).parts
    assert parses == [1]


def test_a_reading_received_stops_the_startup_until_the_next_one():
    # Render's 512 MB (2026-11-06): what a reading of 12 MB leaves in the server and a process of music21 do not fit. Render
    # sleeps after 15 minutes without use: the next start goes on, with room.
    from backend.parsers import reader
    read = []

    class Missing:
        def missing_sources(self, version):
            return iter([b"one", b"two"])

    assert reader.ask_for_turn()
    reader.end_turn()
    prepare_missing_works(Missing(), Missing(), read_work=lambda kind, source: read.append(source))
    assert read == [], "a reading came first: nothing is read until the next start"
