"""Concerts of each user (author's plan, 2026-10-06): date, programme of works in concert order and a
weekly rehearsal pattern; rehearsals belong to at most one concert and the director reviews them
block by block. Another user's concert answers 404."""
import pytest

from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)
from backend.test.test_rehearsal_api import rehearsal

pytestmark = pytest.mark.real_auth


def concert(work_ids, **changes):
    body = {"title": "Concierto de Santa Cecilia", "date": "2026-11-22", "time": "12:00", "place": "Auditorio",
            "notes": "Programa de otoño", "work_ids": work_ids,
            "schedule": {"weekdays": [1, 3], "time": "20:00", "duration_minutes": 120, "start_date": "2026-10-13"}}
    return {**body, **changes}


def test_a_concert_keeps_its_programme_in_concert_order_and_belongs_to_its_owner(clients):
    ana, berta = clients
    first = analyze(ana).json()
    second = analyze(ana, "high_density.musicxml").json()

    created = ana.post("/concerts", json=concert([second["work_id"], first["work_id"]]))

    assert created.status_code == 201
    saved = created.json()
    assert saved["works"] == [{"id": second["work_id"], "title": second["title"]}, {"id": first["work_id"], "title": first["title"]}]
    assert saved["schedule"] == {"weekdays": [1, 3], "time": "20:00", "duration_minutes": 120, "start_date": "2026-10-13"}
    assert saved["rehearsals"] == []
    assert ana.get("/concerts/" + saved["id"]).json() == saved
    assert [item["id"] for item in ana.get("/concerts").json()["concerts"]] == [saved["id"]]
    assert berta.get("/concerts").json() == {"concerts": []}
    for request in (berta.get, berta.delete):
        assert request("/concerts/" + saved["id"]).status_code == 404
    assert berta.put("/concerts/" + saved["id"], json=concert([])).status_code == 404


def test_a_concert_can_be_edited_and_deleting_it_keeps_its_rehearsals(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/concerts", json=concert([work_id])).json()
    linked = ana.post("/rehearsals", json=rehearsal(work_id, concert_id=saved["id"], phase="reading", fixed=True)).json()

    assert linked["concert_id"] == saved["id"] and linked["phase"] == "reading" and linked["fixed"] is True
    assert [item["id"] for item in ana.get("/concerts/" + saved["id"]).json()["rehearsals"]] == [linked["id"]]
    edited = ana.put("/concerts/" + saved["id"], json=concert([work_id], title="Concierto de Navidad", schedule=None))
    assert edited.status_code == 200 and edited.json()["title"] == "Concierto de Navidad" and edited.json()["schedule"] is None

    assert ana.delete("/concerts/" + saved["id"]).status_code == 204
    assert ana.get("/concerts/" + saved["id"]).status_code == 404
    assert ana.get("/rehearsals/" + linked["id"]).json()["concert_id"] is None


@pytest.mark.parametrize("changes", [
    {"title": ""}, {"title": "x" * 201}, {"date": "22-11-2026"}, {"time": "24:00"}, {"notes": "x" * 2001},
    {"schedule": {"weekdays": [7], "time": "20:00", "duration_minutes": 120, "start_date": "2026-10-13"}},
    {"schedule": {"weekdays": [1], "time": "20:00", "duration_minutes": 5, "start_date": "2026-10-13"}},
    {"schedule": {"weekdays": [], "time": "20:00", "duration_minutes": 120, "start_date": "2026-10-13"}},
])
def test_concert_fields_are_validated(clients, changes):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    assert ana.post("/concerts", json=concert([work_id], **changes)).status_code == 422


def test_concerts_and_their_rehearsals_only_use_the_owners_data(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    other_work = analyze(berta).json()["work_id"]
    other_concert = berta.post("/concerts", json=concert([other_work])).json()["id"]

    assert ana.post("/concerts", json=concert([other_work])).status_code == 422
    assert ana.post("/rehearsals", json=rehearsal(work_id, concert_id=other_concert)).status_code == 422
    assert ana.post("/rehearsals", json=rehearsal(work_id, phase="ensayo")).status_code == 422


def test_the_director_reviews_a_rehearsal_block_by_block(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/rehearsals", json=rehearsal(work_id)).json()
    review = {"notes": "Buen ensayo; los clarinetes siguen justos.",
              "blocks": [{"status": "resolved", "note": ""}, {"status": "pending", "note": "Afinación del c. 3"},
                         {"status": "improve", "note": ""}]}

    reviewed = ana.put("/rehearsals/" + saved["id"] + "/review", json=review)

    assert reviewed.status_code == 200
    body = reviewed.json()
    assert body["reviewed_at"] and body["review_notes"] == review["notes"]
    assert [block["review"] for block in body["blocks"]] == review["blocks"]
    assert ana.get("/rehearsals/" + saved["id"]).json()["blocks"][1]["review"]["note"] == "Afinación del c. 3"
    assert berta.put("/rehearsals/" + saved["id"] + "/review", json=review).status_code == 404
    one_block = {"notes": "", "blocks": [{"status": "resolved", "note": ""}]}
    assert ana.put("/rehearsals/" + saved["id"] + "/review", json=one_block).status_code == 422, "one review per block"
    unknown = {"notes": "", "blocks": [{"status": "regular", "note": ""}] * 3}
    assert ana.put("/rehearsals/" + saved["id"] + "/review", json=unknown).status_code == 422


def test_editing_a_reviewed_agenda_keeps_the_reviews_it_sends_back(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/rehearsals", json=rehearsal(work_id)).json()
    reviewed = ana.put("/rehearsals/" + saved["id"] + "/review", json={"notes": "", "blocks": [
        {"status": "resolved", "note": ""}, {"status": "pending", "note": "x"}, {"status": "improve", "note": ""}]}).json()

    blocks = [{key: value for key, value in block.items() if key not in ("work_title",)} for block in reviewed["blocks"]]
    again = ana.put("/rehearsals/" + saved["id"], json=rehearsal(work_id, blocks=blocks)).json()

    assert [block["review"]["status"] for block in again["blocks"]] == ["resolved", "pending", "improve"]


SERIES = {"weekdays": [1, 3], "time": "20:00", "duration_minutes": 90, "start_date": "2026-10-13"}


def saved_blocks(planned):
    """The agenda the editor would save from a planned rehearsal."""
    return [{"title": block["type"], "minutes": block["minutes"], "work_id": block["work_id"], "group": "tutti"}
            for block in planned["blocks"]]


def apply(client, concert_id, plan, today):
    items = [{"id": item["id"], "date": item["date"], "time": item["time"], "duration_minutes": item["duration_minutes"],
              "phase": item["phase"], "work_ids": item["work_ids"], "blocks": saved_blocks(item)} for item in plan]
    return client.put("/concerts/" + concert_id + "/rehearsals", json={"today": today, "rehearsals": items})


def test_the_app_proposes_the_series_of_rehearsals_up_to_the_concert_without_saving_it(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    concert_id = ana.post("/concerts", json=concert([work_id], date="2026-10-29", schedule=SERIES)).json()["id"]

    response = ana.post("/concerts/" + concert_id + "/plan", json={"today": "2026-10-12"})

    assert response.status_code == 200
    plan = response.json()["rehearsals"]
    assert [(item["date"], item["phase"]) for item in plan] == [
        ("2026-10-13", "reading"), ("2026-10-15", "passages"), ("2026-10-20", "passages"),
        ("2026-10-22", "integration"), ("2026-10-27", "general")]
    assert all(item["id"] is None and item["time"] == "20:00" for item in plan)
    assert [block["type"] for block in plan[-1]["blocks"]] == ["warmup", "runthrough"]
    assert ana.get("/concerts/" + concert_id).json()["rehearsals"] == [], "a proposal is not saved"
    assert berta.post("/concerts/" + concert_id + "/plan", json={"today": "2026-10-12"}).status_code == 404


def test_a_concert_without_pattern_nor_rehearsals_cannot_be_planned(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    concert_id = ana.post("/concerts", json=concert([work_id], schedule=None)).json()["id"]
    assert ana.post("/concerts/" + concert_id + "/plan", json={"today": "2026-10-12"}).status_code == 422


def test_after_a_review_only_the_next_unreviewed_and_not_fixed_rehearsals_are_replanned(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    concert_id = ana.post("/concerts", json=concert([work_id], date="2026-10-29", schedule=SERIES)).json()["id"]
    plan = ana.post("/concerts/" + concert_id + "/plan", json={"today": "2026-10-12"}).json()["rehearsals"]
    assert apply(ana, concert_id, plan, "2026-10-12").status_code == 200
    series = ana.get("/concerts/" + concert_id).json()["rehearsals"]
    assert [item["phase"] for item in series] == ["reading", "passages", "passages", "integration", "general"]
    first, second = (ana.get("/rehearsals/" + item["id"]).json() for item in series[:2])
    ana.put("/rehearsals/" + first["id"] + "/review", json={"notes": "", "blocks": [
        {"status": "pending", "note": ""} for _ in first["blocks"]]})
    keep = {key: second[key] for key in ("date", "time", "duration_minutes", "phase")}
    keep["work_ids"] = [item["id"] for item in second["works"]]
    ana.put("/rehearsals/" + second["id"], json={**keep, "concert_id": concert_id, "fixed": True, "blocks": [
        {key: block[key] for key in ("title", "minutes", "work_id", "group")} for block in second["blocks"]]})

    replanned = ana.post("/concerts/" + concert_id + "/plan", json={"today": "2026-10-14"}).json()

    assert [item["id"] for item in replanned["rehearsals"]] == [item["id"] for item in series[2:]]
    assert [item["phase"] for item in replanned["rehearsals"]] == ["passages", "integration", "general"]
    assert set(replanned["kept"]) == {first["id"], second["id"]}
    assert apply(ana, concert_id, replanned["rehearsals"], "2026-10-14").status_code == 200
    reviewed_again = [{**replanned["rehearsals"][0], "id": first["id"]}]
    assert apply(ana, concert_id, reviewed_again, "2026-10-14").status_code == 422, "a reviewed rehearsal is never replaced"


def test_priorities_from_the_last_review_are_what_was_left_pending_or_to_improve(clients):
    ana, berta = clients
    work = analyze(ana).json()
    older = ana.post("/rehearsals", json=rehearsal(work["work_id"], date="2026-10-13")).json()
    latest = ana.post("/rehearsals", json=rehearsal(work["work_id"], date="2026-10-15")).json()
    ana.put("/rehearsals/" + older["id"] + "/review", json={"notes": "", "blocks": [{"status": "pending", "note": "antiguo"}] * 3})
    ana.put("/rehearsals/" + latest["id"] + "/review", json={"notes": "", "blocks": [
        {"status": "resolved", "note": ""}, {"status": "pending", "note": "Entradas de clarinetes"}, {"status": "improve", "note": ""}]})

    priorities = ana.get("/rehearsals/priorities").json()["priorities"]

    assert priorities == [{"rehearsal_id": latest["id"], "date": "2026-10-15", "work_id": work["work_id"], "title": work["title"],
                           "block": "Pasajes prioritarios", "sections": ["Clarinetes"], "parts": ["Clarinet"], "measure_range": "1-4",
                           "status": "pending", "note": "Entradas de clarinetes", "origin": "review"}]
    assert berta.get("/rehearsals/priorities").json() == {"priorities": []}
