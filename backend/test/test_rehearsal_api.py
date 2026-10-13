"""Saved rehearsals of each user (F2a of the interface proposal, 2026-10-05): date, time, duration,
place, works, objectives and an agenda of ordered blocks. Another user's rehearsal answers 404."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


def rehearsal(work_id, **changes):
    body = {
        "date": "2026-10-20", "time": "19:00", "duration_minutes": 60, "place": "Sede de la banda",
        "objectives": "Entradas de maderas", "work_ids": [work_id],
        "blocks": [
            {"title": "Calentamiento", "minutes": 15, "objective": "Afinación y escalas", "group": "warmup"},
            {"title": "Pasajes prioritarios", "minutes": 25, "objective": "Clarinetes", "work_id": work_id,
             "measures": "1-4", "sections": ["Clarinetes"], "group": "clarinets", "parts": ["Clarinet"]},
            {"title": "Tutti", "minutes": 20, "objective": "Juntar", "group": "tutti"},
        ],
    }
    return {**body, **changes}


def test_a_rehearsal_is_saved_with_its_agenda_and_belongs_to_its_owner(clients):
    ana, berta = clients
    work = analyze(ana).json()

    created = ana.post("/rehearsals", json=rehearsal(work["work_id"]))

    assert created.status_code == 201
    saved = created.json()
    assert saved["date"] == "2026-10-20" and saved["time"] == "19:00" and saved["duration_minutes"] == 60
    assert saved["works"] == [{"id": work["work_id"], "title": work["title"]}]
    assert [(block["title"], block["minutes"]) for block in saved["blocks"]] == [
        ("Calentamiento", 15), ("Pasajes prioritarios", 25), ("Tutti", 20)]
    assert saved["blocks"][1]["work_id"] == work["work_id"] and saved["blocks"][1]["sections"] == ["Clarinetes"]
    # The type of each block colours the agenda calendar (author's request, 2026-10-05).
    assert [block["group"] for block in saved["blocks"]] == ["warmup", "clarinets", "tutti"]
    # The parts of each block open the score at its passage with only its instruments.
    assert [block["parts"] for block in saved["blocks"]] == [[], ["Clarinet"], []]
    assert ana.get("/rehearsals/" + saved["id"]).json() == saved
    assert [item["id"] for item in ana.get("/rehearsals").json()["rehearsals"]] == [saved["id"]]
    assert berta.get("/rehearsals").json() == {"rehearsals": []}
    for request in (berta.get, berta.delete):
        assert request("/rehearsals/" + saved["id"]).status_code == 404
    assert berta.put("/rehearsals/" + saved["id"], json=rehearsal(work["work_id"])).status_code == 404


def test_a_rehearsal_can_work_on_several_works(clients):
    ana, _ = clients
    first = analyze(ana).json()
    second = analyze(ana, "high_density.musicxml").json()
    body = rehearsal(first["work_id"], work_ids=[first["work_id"], second["work_id"]], blocks=[
        {"title": "Persis", "minutes": 20, "work_id": first["work_id"], "measures": "1-4"},
        {"title": "Spania", "minutes": 20, "work_id": second["work_id"], "measures": "9-16"},
        {"title": "Tutti", "minutes": 20},
    ])

    saved = ana.post("/rehearsals", json=body).json()

    assert saved["works"] == [{"id": first["work_id"], "title": first["title"]},
                              {"id": second["work_id"], "title": second["title"]}]
    assert [block["work_id"] for block in saved["blocks"]] == [first["work_id"], second["work_id"], None]
    # Each block says which work is being rehearsed in it (author's request, 2026-10-05).
    assert [block["work_title"] for block in saved["blocks"]] == [first["title"], second["title"], None]


def test_the_agenda_can_be_edited_reordered_and_the_rehearsal_deleted(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/rehearsals", json=rehearsal(work_id)).json()
    blocks = list(reversed(saved["blocks"]))[:2]
    blocks[0] = {**blocks[0], "minutes": 30}

    updated = ana.put("/rehearsals/" + saved["id"], json=rehearsal(work_id, duration_minutes=45, blocks=blocks))

    assert updated.status_code == 200
    assert [(block["title"], block["minutes"]) for block in updated.json()["blocks"]] == [("Tutti", 30), ("Pasajes prioritarios", 25)]
    assert updated.json()["duration_minutes"] == 45
    assert ana.delete("/rehearsals/" + saved["id"]).status_code == 204
    assert ana.get("/rehearsals/" + saved["id"]).status_code == 404


def test_rehearsals_are_listed_by_date_and_time(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    for date, time in (("2026-11-02", "18:00"), ("2026-10-20", "20:00"), ("2026-10-20", "19:00")):
        ana.post("/rehearsals", json=rehearsal(work_id, date=date, time=time))

    listed = ana.get("/rehearsals").json()["rehearsals"]

    assert [(item["date"], item["time"]) for item in listed] == [
        ("2026-10-20", "19:00"), ("2026-10-20", "20:00"), ("2026-11-02", "18:00")]


@pytest.mark.parametrize("changes", [
    {"duration_minutes": 5}, {"duration_minutes": 601}, {"date": "20-10-2026"}, {"time": "25:00"},
    {"place": "x" * 201}, {"objectives": "x" * 2001},
    {"blocks": [{"title": "Calentamiento", "minutes": 0}]},
    {"blocks": [{"title": "", "minutes": 10}]},
    {"blocks": [{"title": "Bloque", "minutes": 1}] * 51},
    {"blocks": [{"title": "Bloque", "minutes": 10, "sections": ["x" * 81]}]},
    {"blocks": [{"title": "Bloque", "minutes": 10, "group": "violines"}]},
    {"blocks": [{"title": "Bloque", "minutes": 10, "parts": ["x" * 121]}]},
])
def test_rehearsal_fields_are_validated(clients, changes):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    assert ana.post("/rehearsals", json=rehearsal(work_id, **changes)).status_code == 422


def test_a_rehearsal_only_uses_its_owners_works(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    other_work = analyze(berta).json()["work_id"]

    assert ana.post("/rehearsals", json=rehearsal(other_work)).status_code == 422
    unknown_block_work = rehearsal(work_id, blocks=[{"title": "Bloque", "minutes": 10, "work_id": other_work}])
    assert ana.post("/rehearsals", json=unknown_block_work).status_code == 422


def test_deleting_a_work_keeps_the_rehearsal_without_it(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/rehearsals", json=rehearsal(work_id)).json()

    ana.delete("/works/" + work_id)
    kept = ana.get("/rehearsals/" + saved["id"]).json()

    assert kept["works"] == []
    assert [block["work_id"] for block in kept["blocks"]] == [None, None, None]
    assert [block["title"] for block in kept["blocks"]] == ["Calentamiento", "Pasajes prioritarios", "Tutti"]


def test_rehearsals_need_a_session(clients):
    """With the real repositories: without them the session check answered 503 instead of 401."""
    client = TestClient(app)
    assert client.get("/rehearsals").status_code == 401


def test_the_app_proposes_an_agenda_for_the_chosen_works_without_saving_it(clients):
    ana, _ = clients
    first = analyze(ana).json()
    second = analyze(ana, "high_density.musicxml").json()

    response = ana.post("/rehearsals/proposal", json={"work_ids": [first["work_id"], second["work_id"]], "duration_minutes": 60})

    assert response.status_code == 200
    proposal = response.json()
    assert proposal["blocks"][0]["type"] == "warmup" and proposal["blocks"][0]["work_title"] is None
    titles = {block["work_title"] for block in proposal["blocks"][1:]}
    assert titles == {first["title"], second["title"]}, "every block names its work"
    assert sum(block["minutes"] for block in proposal["blocks"]) == 60
    assert ana.get("/rehearsals").json() == {"rehearsals": []}, "a proposal is not saved"


def test_a_proposal_only_uses_the_owners_works_and_a_valid_duration(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    other = analyze(berta).json()["work_id"]

    assert ana.post("/rehearsals/proposal", json={"work_ids": [other], "duration_minutes": 60}).status_code == 422
    assert ana.post("/rehearsals/proposal", json={"work_ids": [work_id], "duration_minutes": 5}).status_code == 422


def test_a_rehearsal_says_when_its_agenda_was_last_planned(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    saved = ana.post("/rehearsals", json=rehearsal(work_id)).json()

    replanned = ana.put("/rehearsals/" + saved["id"], json=rehearsal(work_id, duration_minutes=45)).json()

    assert saved["updated_at"] and replanned["updated_at"] > saved["updated_at"]


def test_a_rehearsal_is_explained_to_its_owner_with_what_the_last_review_left_pending(clients):
    """«¿Por qué este plan?» (step 20): in demo mode, citing its own blocks and the last review."""
    ana, berta = clients
    work_id = analyze(ana, "evaluation_study.musicxml").json()["work_id"]
    held = ana.post("/rehearsals", json=rehearsal(work_id, date="2026-10-13")).json()
    review = [{"status": "resolved", "note": ""}, {"status": "pending", "note": "Afinación"}, {"status": "improve", "note": ""}]
    assert ana.put("/rehearsals/" + held["id"] + "/review", json={"notes": "", "blocks": review}).status_code == 200
    next_one = ana.post("/rehearsals", json=rehearsal(work_id)).json()

    response = ana.get("/rehearsals/" + next_one["id"] + "/explanation")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo" and body["fallback_reason"] is None
    assert body["explanation"]["summary"].startswith("Ensayo de 60 minutos.")
    assert set(body["blocks"]) == {"B1", "B2", "B3"} and body["blocks"]["B2"]["work_id"] == work_id
    assert any("pendiente" in reason["text"] for reason in body["explanation"]["reasons"])
    assert berta.get("/rehearsals/" + next_one["id"] + "/explanation").status_code == 404
