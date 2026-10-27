"""Bands of each director (decided 2026-10-06): several fixed templates such as «Unió
Musical d'Albalat dels Sorells», with locality, rehearsal days, the full instrumentation and a level
per section. One band is active: analyses and BandFit use its template. Another user's band is 404."""
import pytest

from backend.test.test_concert_api import concert
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


def band(**changes):
    body = {"name": "Unió Musical d'Albalat dels Sorells", "locality": "Albalat dels Sorells", "place": "Casa de la Música",
            "rehearsal_weekdays": [1, 3], "rehearsal_time": "20:00", "rehearsal_minutes": 120,
            "profile": {"flute": 3, "clarinet.bb": 11, "percussion": 4}, "section_levels": {"clarinets": 4, "high_brass": 3}}
    return {**body, **changes}


def test_a_director_keeps_several_bands_and_the_first_one_is_active(clients):
    ana, berta = clients

    first = ana.post("/bands", json=band())
    second = ana.post("/bands", json=band(name="Banda juvenil", profile={"flute": 2}, section_levels={}))

    assert first.status_code == 201 and second.status_code == 201
    saved = first.json()
    assert saved["active"] is True and second.json()["active"] is False
    assert saved["profile"] == {"flute": 3, "clarinet.bb": 11, "percussion": 4}
    assert saved["section_levels"] == {"clarinets": 4, "high_brass": 3}
    assert saved["rehearsal_weekdays"] == [1, 3] and saved["locality"] == "Albalat dels Sorells"
    assert [item["name"] for item in ana.get("/bands").json()["bands"]] == ["Unió Musical d'Albalat dels Sorells", "Banda juvenil"]
    assert ana.get("/bands/" + saved["id"]).json() == saved
    assert berta.get("/bands").json() == {"bands": []}
    for request in (berta.get, berta.delete):
        assert request("/bands/" + saved["id"]).status_code == 404
    assert berta.put("/bands/" + saved["id"], json=band()).status_code == 404


def test_the_active_band_is_the_template_of_the_analyses(clients):
    ana, _ = clients
    ana.post("/bands", json=band())
    youth = ana.post("/bands", json=band(name="Banda juvenil", profile={"clarinet.bb": 0})).json()

    assert ana.get("/band").json() == {"profile": {"flute": 3, "clarinet.bb": 11, "percussion": 4}}
    assert ana.post("/bands/" + youth["id"] + "/activate").json()["active"] is True
    assert ana.get("/band").json() == {"profile": {"clarinet.bb": 0}}
    assert [item["active"] for item in ana.get("/bands").json()["bands"]] == [False, True], "only one band is active"
    assert analyze(ana).json()["band_fit"]["requirements"][0]["available"] == 0
    assert ana.patch("/band", json={"profile": {"flute": 1}}).json() == {"profile": {"clarinet.bb": 0, "flute": 1}}
    assert ana.get("/bands/" + youth["id"]).json()["profile"] == {"clarinet.bb": 0, "flute": 1}


def test_a_director_without_bands_gets_one_when_the_template_is_first_saved(clients):
    ana, _ = clients
    assert ana.get("/band").json() == {"profile": {}}

    ana.patch("/band", json={"profile": {"clarinet.bb": 2}})

    [created] = ana.get("/bands").json()["bands"]
    assert created["name"] == "Mi banda" and created["active"] is True and created["profile"] == {"clarinet.bb": 2}


def test_deleting_the_active_band_activates_the_oldest_remaining_one(clients):
    ana, _ = clients
    first = ana.post("/bands", json=band()).json()
    second = ana.post("/bands", json=band(name="Banda juvenil")).json()

    assert ana.delete("/bands/" + first["id"]).status_code == 204
    assert ana.get("/bands/" + second["id"]).json()["active"] is True


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "x" * 201}, {"locality": "x" * 201}, {"rehearsal_weekdays": [7]},
    {"rehearsal_time": "25:00"}, {"rehearsal_minutes": 5}, {"profile": {"flute": -1}},
    {"section_levels": {"clarinets": 7}}, {"section_levels": {"violines": 3}},
])
def test_band_fields_are_validated(clients, changes):
    ana, _ = clients
    assert ana.post("/bands", json=band(**changes)).status_code == 422


def test_a_concert_is_played_by_one_of_the_directors_bands(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]
    own = ana.post("/bands", json=band()).json()
    other = berta.post("/bands", json=band()).json()

    saved = ana.post("/concerts", json=concert([work_id], band_id=own["id"])).json()

    assert saved["band"] == {"id": own["id"], "name": own["name"]}
    assert ana.post("/concerts", json=concert([work_id], band_id=other["id"])).status_code == 422
    ana.delete("/bands/" + own["id"])
    assert ana.get("/concerts/" + saved["id"]).json()["band"] is None
