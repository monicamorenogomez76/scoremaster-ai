"""The director corrects a note of a saved work (2026-11-22): the file, its model, its audio and its analysis follow,
without reading the work with music21 again; the corrections are listed and the last one is undone."""
from hashlib import sha256

import pytest

from backend.parsers import playback
from backend.test.test_library_api import clients  # noqa: F401  (signed-in Ana and Berta over PostgreSQL)
from backend.test.test_note_corrections import work

pytestmark = pytest.mark.real_auth
REST_TO_D = {"part_id": "P1", "measure": 1, "offset": 1 / 3, "old": None, "new": ["D", 0, 5]}
B_TO_B_FLAT = {"part_id": "P1", "measure": 2, "offset": 0.0, "old": ["B", 0, 4], "new": ["B", -1, 4]}


def upload(client) -> str:
    answer = client.post("/analyze", files={"file": ("clarinete.musicxml", work(), "application/xml")})
    assert answer.status_code == 200
    return answer.json()["work_id"]


def test_a_corrected_note_changes_the_file_the_audio_and_the_analysis_without_music21(clients, monkeypatch):  # noqa: F811
    ana, berta = clients
    work_id = upload(ana)
    playback.prepare_playback(work())
    analysis = ana.get("/works/" + work_id).json()["analysis_id"]

    def never(*_):
        raise AssertionError("music21 read the work again")
    monkeypatch.setattr("backend.app.stored_scores.parse_musicxml", never)
    monkeypatch.setattr("backend.parsers.playback._read_timeline", never)

    answer = ana.post(f"/works/{work_id}/corrections", json=REST_TO_D)
    assert answer.status_code == 200, answer.text
    assert answer.json()["corrections"] == [
        {"part": "Clarinet in Bb", "measure": "1", "old": None, "new": ["D", 0, 5], "id": answer.json()["corrections"][0]["id"],
         "created_at": answer.json()["corrections"][0]["created_at"]}]
    corrected = ana.get(f"/works/{work_id}/file").content
    assert b"<step>D</step>" in corrected
    assert playback._ready(sha256(corrected).hexdigest(), None) is not None, "the audio is ready for the corrected file"
    assert ana.get("/works/" + work_id).json()["analysis_id"] != analysis, "analysed again"
    assert berta.post(f"/works/{work_id}/corrections", json=B_TO_B_FLAT).status_code == 404
    assert berta.get(f"/works/{work_id}/corrections").status_code == 404

    assert ana.post(f"/works/{work_id}/corrections", json=B_TO_B_FLAT).status_code == 200
    assert len(ana.get(f"/works/{work_id}/corrections").json()["corrections"]) == 2
    undone = ana.delete(f"/works/{work_id}/corrections/last")
    assert undone.status_code == 200 and len(undone.json()["corrections"]) == 1
    back = ana.get(f"/works/{work_id}/file").content
    assert b"<alter>-1</alter>" not in back and b"<step>D</step>" in back, "only the last correction is undone"


def test_a_note_that_is_not_there_is_refused_and_nothing_changes(clients):  # noqa: F811
    ana, _ = clients
    work_id = upload(ana)
    answer = ana.post(f"/works/{work_id}/corrections", json={**B_TO_B_FLAT, "old": ["D", 0, 4]})
    assert answer.status_code == 422 and "vuelve a abrir" in answer.json()["detail"]
    assert ana.get(f"/works/{work_id}/file").content == work()
    assert ana.get(f"/works/{work_id}/corrections").json()["corrections"] == []
    assert ana.delete(f"/works/{work_id}/corrections/last").status_code == 404
    assert ana.post(f"/works/{work_id}/corrections", json={**B_TO_B_FLAT, "new": ["H", 0, 4]}).status_code == 422


def test_the_parts_and_the_notes_of_a_measure_are_listed_for_the_owner(clients):  # noqa: F811
    ana, berta = clients
    work_id = upload(ana)
    assert ana.get(f"/works/{work_id}/notes").json() == {"parts": [{"id": "P1", "name": "Clarinet in Bb"}]}
    found = ana.get(f"/works/{work_id}/notes", params={"part_id": "P1", "measure": "2"}).json()
    assert found["measure"] == 2 and [item["pitch"] for item in found["notes"]] == [["B", 0, 4], ["C", 0, 5], ["E", 0, 5]]
    assert ana.get(f"/works/{work_id}/notes", params={"part_id": "P1", "measure": "40"}).status_code == 404
    assert berta.get(f"/works/{work_id}/notes").status_code == 404


def test_the_changes_made_on_the_score_are_saved_together_and_analysed_once(clients, monkeypatch):  # noqa: F811
    """Edited on the score as in a notation program (2026-11-23): the director changes several notes, sees them at once,
    and saves them together; the measures are named by the number the score prints."""
    ana, berta = clients
    work_id = upload(ana)
    playback.prepare_playback(work())
    analyses = []
    import backend.app.correction_routes as routes
    monkeypatch.setattr(routes, "analyse_again", lambda *args: analyses.append(args))
    changes = [{"part_id": "P1", "number": "1", "offset": 1 / 3, "old": None, "new": ["D", 0, 5]},
               {"part_id": "P1", "number": "2", "offset": 0.0, "old": ["B", 0, 4], "new": ["B", -1, 4]}]
    answer = ana.post(f"/works/{work_id}/corrections/batch", json={"corrections": changes})
    assert answer.status_code == 200, answer.text
    assert [item["measure"] for item in answer.json()["corrections"]] == ["1", "2"]
    corrected = ana.get(f"/works/{work_id}/file").content
    assert b"<step>D</step>" in corrected and b"<alter>-1</alter>" in corrected
    assert len(analyses) == 1, "one analysis for all the changes"
    assert playback._ready(sha256(corrected).hexdigest(), None) is not None

    wrong = [changes[0], {"part_id": "P1", "number": "2", "offset": 0.0, "old": ["A", 0, 4], "new": ["B", 0, 4]}]
    assert ana.post(f"/works/{work_id}/corrections/batch", json={"corrections": wrong}).status_code == 422
    assert ana.get(f"/works/{work_id}/file").content == corrected, "nothing is saved when one change cannot be made"
    assert berta.post(f"/works/{work_id}/corrections/batch", json={"corrections": changes}).status_code == 404
    assert ana.post(f"/works/{work_id}/corrections/batch", json={"corrections": []}).status_code == 422


def test_a_duration_changed_on_the_score_is_saved_and_undone_as_the_measure_was(clients, monkeypatch):  # noqa: F811
    from backend.test.test_note_corrections import plain
    ana, _ = clients
    answer = ana.post("/analyze", files={"file": ("flauta.musicxml", plain(), "application/xml")})
    work_id = answer.json()["work_id"]
    playback.prepare_playback(plain())

    def never(*_):
        raise AssertionError("music21 read the work again")
    monkeypatch.setattr("backend.app.stored_scores.parse_musicxml", never)
    monkeypatch.setattr("backend.parsers.playback._read_timeline", never)
    longer = {"part_id": "P1", "number": "1", "offset": 0.0, "old": ["C", 0, 5], "new": ["C", 0, 5], "new_type": "quarter"}
    saved = ana.post(f"/works/{work_id}/corrections/batch", json={"corrections": [longer]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["corrections"][0] | {"id": None, "created_at": None} == {
        "id": None, "created_at": None, "part": "Flute", "measure": "1", "old": ["C", 0, 5], "new": ["C", 0, 5],
        "old_type": "eighth", "old_dots": 0, "new_type": "quarter", "new_dots": 0}
    assert ana.get(f"/works/{work_id}/file").content.count(b"<type>eighth</type>") == 2
    assert ana.post(f"/works/{work_id}/corrections/batch", json={"corrections": [
        {**longer, "offset": 1.0, "old": ["E", 0, 5], "new": ["E", 0, 5], "new_dots": 1}]}).status_code == 422
    assert ana.delete(f"/works/{work_id}/corrections/last").status_code == 200
    back = ana.get(f"/works/{work_id}/file").content
    assert back.count(b"<type>eighth</type>") == 4 and b"<step>D</step>" in back, "the measure as it was"
