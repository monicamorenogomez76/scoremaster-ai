"""Library of works and band per user over HTTP (plan phase 2)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import auth_routes
from backend.app.dependencies import get_account_repository, get_analysis_repository, get_library_repository
from backend.app.main import app
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository

pytestmark = pytest.mark.real_auth
SCORES = Path(__file__).resolve().parents[2] / "test-scores"


@pytest.fixture
def clients(postgres_engine):
    auth_routes.LIMITER.reset()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    app.dependency_overrides[get_analysis_repository] = lambda: PostgresAnalysisRepository(postgres_engine)
    app.dependency_overrides[get_library_repository] = lambda: PostgresLibraryRepository(postgres_engine)
    signed_in = []
    for name in ("ana", "berta"):
        client = TestClient(app)
        csrf = client.post("/auth/register", json={"email": name + "@banda.org", "password": "una contraseña larga",
                                                   "display_name": name}).json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        signed_in.append(client)
    try:
        yield signed_in
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def analyze(client, name="high_register.musicxml", profile=None):
    with (SCORES / name).open("rb") as musicxml:
        data = {} if profile is None else {"band_profile": json.dumps(profile)}
        return client.post("/analyze", files={"file": (name, musicxml, "application/xml")}, data=data)


def test_an_analysis_is_saved_as_a_work_of_its_owner(clients):
    ana, berta = clients
    response = analyze(ana)

    assert response.status_code == 200
    work_id = response.json()["work_id"]
    [work] = ana.get("/works").json()["works"]
    assert work["id"] == work_id and work["file_name"] == "high_register.musicxml"
    assert work["summary"]["compatibility_percent"] == response.json()["band_fit"]["compatibility_percent"]
    assert berta.get("/works").json()["works"] == []


def test_a_saved_work_reopens_without_uploading_it_again(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]

    reopened = ana.get("/works/" + work_id)
    assert reopened.status_code == 200
    assert reopened.json()["work_id"] == work_id and reopened.json()["title"]
    original = ana.get("/works/" + work_id + "/file")
    assert original.content == (SCORES / "high_register.musicxml").read_bytes()
    assert "high_register.musicxml" in original.headers["content-disposition"]


def test_analysing_the_same_file_again_updates_the_work(clients):
    ana, _ = clients
    first = analyze(ana).json()["work_id"]
    again = analyze(ana).json()["work_id"]
    analyze(ana, "high_density.musicxml")

    assert first == again
    assert len(ana.get("/works").json()["works"]) == 2


def test_other_users_cannot_read_or_delete_a_work(clients):
    ana, berta = clients
    work_id = analyze(ana).json()["work_id"]

    for path in ("/works/" + work_id, "/works/" + work_id + "/file"):
        assert berta.get(path).status_code == 404
    assert berta.delete("/works/" + work_id).status_code == 404
    assert ana.get("/works/" + work_id).status_code == 200
    assert ana.get("/works/not-a-uuid").status_code == 404


def test_deleting_a_work_removes_it_and_its_analyses(clients):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]

    assert ana.delete("/works/" + work_id).status_code == 204
    assert ana.get("/works/" + work_id).status_code == 404
    assert ana.get("/works").json()["works"] == []


def test_the_saved_band_completes_the_profile_of_an_analysis(clients):
    ana, berta = clients
    assert ana.patch("/band", json={"profile": {"clarinet.bb": 0}}).status_code == 200
    assert ana.get("/band").json() == {"profile": {"clarinet.bb": 0}}

    band_fit = analyze(ana).json()["band_fit"]
    assert band_fit["requirements"][0]["available"] == 0
    assert analyze(ana, profile={"clarinet.bb": 3}).json()["band_fit"]["requirements"][0]["available"] == 3
    assert berta.get("/band").json() == {"profile": {}}


@pytest.mark.parametrize("profile", [{"clarinet.bb": -1}, {"clarinet.bb": "muchos"}, ["flute"]])
def test_band_updates_are_validated(clients, profile):
    ana, _ = clients
    assert ana.patch("/band", json={"profile": profile}).status_code in (400, 422)


def test_library_endpoints_need_a_session():
    client = TestClient(app)
    assert client.get("/works").status_code == 401
    assert client.get("/band").status_code == 401


def test_the_analysis_estimates_the_duration_of_the_work(clients):
    ana, _ = clients
    duration = analyze(ana).json()["duration"]
    assert duration["seconds"] > 0 and isinstance(duration["assumed_tempo"], bool)


def test_instruments_never_configured_start_with_what_the_work_needs(clients):
    ana, _ = clients
    [requirement] = analyze(ana).json()["band_fit"]["requirements"]
    assert requirement["available"] == requirement["required"]

    ana.patch("/band", json={"profile": {requirement["key"]: 0}})
    assert analyze(ana).json()["band_fit"]["requirements"][0]["available"] == 0
