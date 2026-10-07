"""Passages of the same work are prepared without reading the whole score again (2026-10-07: with
real band scores the author waited 10-20 s per passage, most of it in music21; on Render's free plan
a passage of Persis took more than the 60 s the browser waited)."""
from pathlib import Path

import pytest

from backend.parsers import playback
from backend.parsers.playback import build_playback, prepare_playback

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


def _no_music21(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("music21 should not be needed once the work is prepared")
    monkeypatch.setattr(playback.converter, "parse", fail)
    monkeypatch.setattr(playback.stream.Stream, "toSoundingPitch", fail)
    monkeypatch.setattr(playback, "extract_musicxml", fail)


def test_a_second_passage_of_the_same_score_reuses_the_prepared_timeline(tmp_path, monkeypatch):
    playback.clear_timelines()
    calls = []
    original = playback.converter.parse
    monkeypatch.setattr(playback.converter, "parse", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs))
    copy = tmp_path / "copy.musicxml"
    copy.write_bytes((SCORES / "high_register.musicxml").read_bytes())

    first = build_playback(SCORES / "high_register.musicxml", "Clarinet", 1, 1)
    again = build_playback(copy, "Clarinet", 1, 1)

    assert len(calls) == 1, "the same content is parsed once, whatever the temporary file name"
    assert again == first


@pytest.mark.parametrize("selection, first, last", [
    ("", 0, 999999), ("Clarinet", 1, 1), (["Clarinet"], 1, 1),
])
def test_a_prepared_work_gives_every_passage_without_music21(monkeypatch, selection, first, last):
    playback.clear_timelines()
    fresh = build_playback(SCORES / "high_density.musicxml", selection, first, last)
    playback.clear_timelines()
    prepare_playback((SCORES / "high_density.musicxml").read_bytes())
    _no_music21(monkeypatch)
    assert build_playback(SCORES / "high_density.musicxml", selection, first, last) == fresh


def test_the_endpoint_cuts_a_prepared_work_without_reading_its_xml_again(monkeypatch):
    """Each passage validated the whole XML twice: seconds per passage on a slow server."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    playback.clear_timelines()
    content = (SCORES / "high_density.musicxml").read_bytes()
    expected = build_playback(content, "Clarinet", 1, 1)
    _no_music21(monkeypatch)
    response = TestClient(app).post("/playback", files={"file": ("obra.musicxml", content, "application/xml")},
                                    data={"instrument": "Clarinet", "first_measure": 1, "last_measure": 1})
    assert response.status_code == 200
    assert response.json() == expected


def test_errors_of_a_prepared_work_are_the_same():
    playback.clear_timelines()
    prepare_playback((SCORES / "high_density.musicxml").read_bytes())
    with pytest.raises(ValueError, match="instrumento"):
        build_playback(SCORES / "high_density.musicxml", "Oboe", 1, 1)
    with pytest.raises(ValueError, match="rango"):
        build_playback(SCORES / "high_density.musicxml", "Clarinet", 50, 60)


def test_preparing_a_work_twice_reads_it_once(monkeypatch):
    playback.clear_timelines()
    calls = []
    original = playback.converter.parse
    monkeypatch.setattr(playback.converter, "parse", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs))
    content = (SCORES / "minimal.musicxml").read_bytes()
    prepare_playback(content)
    prepare_playback(content)
    assert len(calls) == 1
    assert playback.prepared_count() == 1


def test_preparing_something_that_is_not_a_score_does_not_fail():
    """The preparation runs in the background: a bad file only means the passage will report the error."""
    playback.clear_timelines()
    prepare_playback(b"not musicxml")
    assert playback.prepared_count() == 0


def test_only_a_few_works_are_kept_in_memory():
    playback.clear_timelines()
    for name in ("minimal.musicxml", "high_density.musicxml", "high_register.musicxml", "large_intervals.musicxml",
                 "measure_with_rest.musicxml"):
        build_playback(SCORES / name, "", 0, 999999)
    assert playback.prepared_count() == 4


def test_how_many_works_are_kept_can_be_changed_for_small_servers(monkeypatch):
    monkeypatch.setenv("PLAYBACK_SCORES_KEPT", "1")
    playback.clear_timelines()
    for name in ("minimal.musicxml", "high_density.musicxml"):
        build_playback(SCORES / name, "", 0, 999999)
    assert playback.prepared_count() == 1


def test_a_prepared_work_does_not_wait_while_another_one_is_being_read():
    """On a slow server reading a work takes minutes; the passages of works already prepared still sound."""
    import threading
    playback.clear_timelines()
    content = (SCORES / "high_density.musicxml").read_bytes()
    prepare_playback(content)
    done, busy = threading.Event(), threading.Event()
    playback._reader.submit(busy.wait, 10)          # another work is being read
    threading.Thread(target=lambda: build_playback(content, "Clarinet", 1, 1) and done.set()).start()
    assert done.wait(5), "the prepared work was cut without waiting for the other one"
    busy.set()
