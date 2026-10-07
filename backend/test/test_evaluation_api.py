"""Evaluation campaigns (steps 16-18, author's decisions, 2026-10-07): the director proposes passages of
her works and invites musicians by email; each musician, with an account, rates every passage
(difficulty 1-6, critical, rehearsal priority 1-5, optional comment) without seeing ScoreLint's
prediction, and may open the whole work. Results are exported with anonymous evaluators."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


def register(name):
    client = TestClient(app)
    csrf = client.post("/auth/register", json={"email": name + "@banda.org", "password": "una contraseña larga",
                                               "display_name": name}).json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf
    return client


def campaign(client, **changes):
    work_ids = [analyze(client, "evaluation_study.musicxml").json()["work_id"], analyze(client, "high_density.musicxml").json()["work_id"]]
    body = {"title": "Dificultad de pasajes de banda", "instructions": "Valora cada pasaje para una banda amateur media.",
            "work_ids": work_ids, "size": 20, **changes}
    return client.post("/evaluations", json=body)


def rating(**changes):
    return {"difficulty": 4, "critical": True, "priority": 3, "comment": "Entradas difíciles", **changes}


def test_the_director_creates_a_campaign_with_proposed_passages_and_their_prediction(clients):
    ana, _ = clients

    created = campaign(ana)

    assert created.status_code == 201
    body = created.json()
    assert body["role"] == "owner" and body["status"] == "draft" and body["passages"]
    first = body["passages"][0]
    assert {"id", "work_id", "work_title", "parts", "measure_range", "label", "snapshot"} <= set(first)
    assert 1 <= first["snapshot"]["grade"] <= 6
    assert [item["id"] for item in ana.get("/evaluations").json()["owned"]] == [body["id"]]


@pytest.mark.parametrize("changes", [{"title": ""}, {"size": 5}, {"size": 81}, {"instructions": "x" * 2001}])
def test_campaign_fields_are_validated(clients, changes):
    ana, _ = clients
    assert campaign(ana, **changes).status_code == 422


def test_only_the_directors_works_can_be_evaluated(clients):
    ana, berta = clients
    other = analyze(berta).json()["work_id"]
    assert ana.post("/evaluations", json={"title": "x", "work_ids": [other], "size": 10}).status_code == 422


def test_invited_musicians_rate_the_passages_without_seeing_the_prediction(clients):
    ana, berta = clients
    body = campaign(ana).json()
    path = "/evaluations/" + body["id"]
    assert ana.put(path + "/invitations", json={"emails": ["BERTA@banda.org", "nadie@banda.org"]}).status_code == 200
    assert berta.get("/evaluations").json()["invited"] == [], "a draft is not shown to the musicians"
    assert ana.post(path + "/status", json={"status": "open"}).json()["status"] == "open"

    [invited] = berta.get("/evaluations").json()["invited"]
    view = berta.get(path).json()
    assert invited["id"] == body["id"] and view["role"] == "evaluator"
    assert all("snapshot" not in item for item in view["passages"]), "the musician never sees ScoreLint's prediction"
    passage = view["passages"][0]
    assert berta.put(path + "/profile", json={"experience_level": "amateur", "main_instrument": "Clarinete"}).status_code == 200
    assert berta.put(path + "/passages/" + passage["id"] + "/rating", json=rating()).status_code == 200
    assert berta.put(path + "/passages/" + passage["id"] + "/rating", json=rating(difficulty=5)).status_code == 200
    again = berta.get(path).json()
    assert again["passages"][0]["rating"] == rating(difficulty=5) and again["profile"]["main_instrument"] == "Clarinete"
    whole = berta.get(path + "/works/" + passage["work_id"] + "/file")
    assert whole.status_code == 200 and whole.content.startswith(b"<?xml"), "the musician may open the whole work"


@pytest.mark.parametrize("changes", [{"difficulty": 0}, {"difficulty": 7}, {"priority": 6}, {"critical": "a veces"},
                                     {"comment": "x" * 501}])
def test_ratings_are_validated(clients, changes):
    ana, berta = clients
    body = campaign(ana).json()
    path = "/evaluations/" + body["id"]
    ana.put(path + "/invitations", json={"emails": ["berta@banda.org"]})
    ana.post(path + "/status", json={"status": "open"})
    passage = body["passages"][0]["id"]
    assert berta.put(path + "/passages/" + passage + "/rating", json=rating(**changes)).status_code == 422


def test_people_not_invited_see_nothing(clients):
    ana, _ = clients
    body = campaign(ana).json()
    path = "/evaluations/" + body["id"]
    ana.post(path + "/status", json={"status": "open"})
    carla = register("carla")
    passage = body["passages"][0]
    assert carla.get(path).status_code == 404
    assert carla.put(path + "/passages/" + passage["id"] + "/rating", json=rating()).status_code == 404
    assert carla.get(path + "/works/" + passage["work_id"] + "/file").status_code == 404
    assert carla.put(path + "/invitations", json={"emails": ["carla@banda.org"]}).status_code == 404


def test_passages_change_only_in_draft_and_ratings_only_while_open(clients):
    ana, berta = clients
    body = campaign(ana).json()
    path = "/evaluations/" + body["id"]
    first, second = body["passages"][0]["id"], body["passages"][1]["id"]
    assert ana.delete(path + "/passages/" + first).status_code == 204
    assert first not in [item["id"] for item in ana.get(path).json()["passages"]]
    ana.put(path + "/invitations", json={"emails": ["berta@banda.org"]})
    ana.post(path + "/status", json={"status": "open"})
    assert ana.delete(path + "/passages/" + second).status_code == 409, "an open campaign keeps its passages"
    ana.post(path + "/status", json={"status": "closed"})
    assert berta.put(path + "/passages/" + second + "/rating", json=rating()).status_code == 409


def test_results_are_exported_with_anonymous_evaluators(clients):
    ana, berta = clients
    body = campaign(ana).json()
    path = "/evaluations/" + body["id"]
    ana.put(path + "/invitations", json={"emails": ["berta@banda.org"]})
    ana.post(path + "/status", json={"status": "open"})
    berta.put(path + "/profile", json={"experience_level": "profesional", "main_instrument": "Trompeta"})
    passage = body["passages"][0]
    berta.put(path + "/passages/" + passage["id"] + "/rating", json=rating())

    exported = ana.get(path + "/export").json()

    [row] = exported["ratings"]
    assert row["passage_id"] == passage["id"] and row["snapshot"] == passage["snapshot"]
    assert row["evaluator"] == "Evaluador 1" and row["experience_level"] == "profesional"
    assert (row["difficulty"], row["critical"], row["priority"]) == (4, True, 3)
    assert "berta" not in str(exported).lower(), "no email or name of the musicians"
    assert len(exported["passages"]) == len(body["passages"])
    assert berta.get(path + "/export").status_code == 404


def test_a_campaign_uses_the_kept_model_of_each_work_without_reading_it_again(clients, postgres_engine, monkeypatch):
    """On Render's free plan reading a band score again took minutes (2026-10-07)."""
    from backend.app import stored_scores
    from backend.app.dependencies import get_score_store
    from backend.infrastructure.prepared_store import PostgresPreparedStore
    app.dependency_overrides[get_score_store] = lambda: PostgresPreparedStore(postgres_engine, "score")
    ana, _ = clients
    work_id = analyze(ana, "evaluation_study.musicxml").json()["work_id"]
    stored_scores.clear_parsed_works()
    monkeypatch.setattr(stored_scores, "parse_musicxml", lambda *args: pytest.fail("the work was read again"))
    assert ana.post("/evaluations", json={"title": "x", "work_ids": [work_id], "size": 10}).status_code == 201
