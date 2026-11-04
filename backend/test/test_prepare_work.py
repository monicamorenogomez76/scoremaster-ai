"""A work read from a PDF is prepared in GitHub's machine (2026-11-04): what it sends must be what Render would have
prepared itself, or Render would answer differently for a work read from a PDF."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from backend.parsers import playback
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.prepare import MAX_PREPARED_BYTES, prepare_work, usable_score, usable_timeline
from backend.parsers.score_codec import SCORE_VERSION, decode_score, encode_score

SCORE = Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml"


def test_the_prepared_work_is_what_render_would_prepare():
    content = SCORE.read_bytes()
    prepared = prepare_work(content)
    assert prepared["sha256"] == hashlib.sha256(content).hexdigest()
    assert prepared["score_version"] == SCORE_VERSION and prepared["timeline_version"] == playback.TIMELINE_VERSION
    assert decode_score(base64.b64decode(prepared["score"])) == parse_musicxml(SCORE)
    timeline = playback._decode(base64.b64decode(prepared["timeline"]))
    assert timeline == playback._read_timeline(content)


def test_what_is_prepared_can_be_used():
    prepared = prepare_work(SCORE.read_bytes())
    assert usable_score(base64.b64decode(prepared["score"]))
    assert usable_timeline(base64.b64decode(prepared["timeline"]))


@pytest.mark.parametrize("check", [usable_score, usable_timeline])
@pytest.mark.parametrize("data", [b"", b"not gzip", gzip.compress(b"not json"), gzip.compress(b"{}"),
                                  gzip.compress(b"[]")])
def test_what_cannot_be_read_is_not_used(check, data):
    assert not check(data)


def test_a_work_without_parts_is_not_used():
    assert not usable_score(gzip.compress(json.dumps({"title": "", "parts": [], "tempo_marks": [],
                                                      "composer": None}).encode()))
    assert not usable_timeline(gzip.compress(json.dumps({"parts": [], "marks": [], "highest_time": 0}).encode()))


@pytest.mark.parametrize("check", [usable_score, usable_timeline])
def test_what_would_fill_the_memory_is_not_opened(check):
    """Render has 512 MB: a few kilobytes of gzip can open into gigabytes."""
    assert not check(gzip.compress(b" " * (MAX_PREPARED_BYTES + 1)))


def test_the_codec_still_reads_what_it_wrote():
    score = parse_musicxml(SCORE)
    assert usable_score(encode_score(score))
