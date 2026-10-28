"""The reader tells ScoreMaster it started before installing anything (2026-10-28), so the director sees «Preparando el
lector» instead of waiting without news. It reads the job from GitHub's event file and needs no package."""
import json

import omr.started as started


def test_the_reader_says_it_started_with_the_job_s_token(tmp_path, monkeypatch, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"client_payload": {"token": "one-time", "callback": "https://sm.test/omr/imports/7"}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    sent = []
    started.main(post=lambda url, body, token: sent.append((url, body, token)))
    assert sent == [("https://sm.test/omr/imports/7/progress", {"pages_done": 0, "pages_total": 0, "stage": "preparing"}, "one-time")]
    assert capsys.readouterr().out.splitlines()[0] == "::add-mask::one-time"


def test_a_failure_to_tell_never_stops_the_reading(tmp_path, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"client_payload": {"token": "t", "callback": "https://sm.test/omr/imports/7"}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))

    def broken(url, body, token):
        raise OSError("no network")

    assert started.main(post=broken) == 0
