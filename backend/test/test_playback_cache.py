"""Passages of the same work are prepared without reading the whole score again (2026-10-07: with
real band scores the author waited 10-20 s per passage, most of it in music21 parsing the file)."""
from pathlib import Path

from backend.parsers import playback
from backend.parsers.playback import build_playback

SCORES = Path(__file__).resolve().parents[2] / "test-scores"


def test_a_second_passage_of_the_same_score_reuses_the_parsed_score(tmp_path, monkeypatch):
    playback.clear_parsed_scores()
    calls = []
    original = playback.converter.parse
    monkeypatch.setattr(playback.converter, "parse", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs))
    copy = tmp_path / "copy.musicxml"
    copy.write_bytes((SCORES / "high_register.musicxml").read_bytes())

    first = build_playback(SCORES / "high_register.musicxml", "Clarinet", 1, 1)
    again = build_playback(copy, "Clarinet", 1, 1)

    assert len(calls) == 1, "the same content is parsed once, whatever the temporary file name"
    assert again == first


def test_the_reused_score_gives_the_same_timeline_as_a_fresh_one():
    playback.clear_parsed_scores()
    fresh = build_playback(SCORES / "high_density.musicxml", "", 0, 999999)
    cached = build_playback(SCORES / "high_density.musicxml", "", 0, 999999)
    playback.clear_parsed_scores()
    assert cached == fresh == build_playback(SCORES / "high_density.musicxml", "", 0, 999999)


def test_only_a_few_scores_are_kept_in_memory():
    playback.clear_parsed_scores()
    for name in ("minimal.musicxml", "high_density.musicxml", "high_register.musicxml", "large_intervals.musicxml",
                 "measure_with_rest.musicxml"):
        build_playback(SCORES / name, "", 0, 999999)
    assert playback.parsed_score_count() == playback.PARSED_SCORES_KEPT == 4
