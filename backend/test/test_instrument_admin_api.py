"""The instrument catalog in PostgreSQL (2026-10-28): the migration loads the seed, the server reads it at startup and
the administration adds or removes names and instruments from Configuración. A name always names one instrument."""
import json

import pytest
from sqlalchemy import text

from backend.app.dependencies import get_instrument_repository
from backend.app.main import app, load_instrument_catalog
from backend.app.work_analysis import refresh_outdated_analyses
from backend.domain.instrument_catalog import (CATALOG_PATH, catalog_version, match_instrument_name,
                                               normalize_instrument_name)
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.test.test_instrument_names_multilingual import NAMES
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


@pytest.fixture
def instruments(clients, postgres_engine, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ana@banda.org")
    app.dependency_overrides[get_instrument_repository] = lambda: PostgresInstrumentRepository(postgres_engine)
    return clients


def test_the_migration_loads_every_instrument_and_name_of_the_seed(postgres_engine):
    seed = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["instruments"]
    with postgres_engine.connect() as connection:
        ids = connection.execute(text("SELECT id FROM instruments WHERE owner_id IS NULL ORDER BY position")).scalars().all()
        names = connection.execute(text("SELECT count(*) FROM instrument_names WHERE owner_id IS NULL")).scalar()
    assert ids == [item["id"] for item in seed]
    assert names == sum(len({normalize_instrument_name(alias) for alias in item["aliases"]}) for item in seed)


def test_the_catalog_read_from_the_database_recognises_the_same_names(postgres_engine):
    load_instrument_catalog(PostgresInstrumentRepository(postgres_engine))
    assert catalog_version() == "instrument-catalog-v5"
    for name, canonical_id in NAMES:
        assert match_instrument_name(name).identity.canonical_id == canonical_id, name


def test_a_name_added_by_the_administration_is_recognised_and_the_works_are_analysed_again(instruments, postgres_engine):
    ana, _ = instruments
    work = analyze(ana).json()["work_id"]
    assert work
    response = ana.post("/admin/instruments/flugelhorn.bb/names", json={"name": "Fiscornio"})
    assert response.status_code == 201, response.text
    assert match_instrument_name("Fiscornio 1").identity.canonical_id == "flugelhorn.bb"
    listed = next(item for item in ana.get("/admin/instruments").json()["instruments"]
                  if item["canonical_id"] == "flugelhorn.bb")
    assert "Fiscornio" in [name["name"] for name in listed["names"]]

    repositories = PostgresAnalysisRepository(postgres_engine), PostgresLibraryRepository(postgres_engine)
    assert refresh_outdated_analyses(*repositories) == 1, "the catalog changed"

    assert ana.delete("/admin/instruments/names/{}".format(response.json()["id"])).status_code == 204
    assert match_instrument_name("Fiscornio 1").identity is None


@pytest.mark.parametrize("name", ["Fliscorn", "FLISCORN", "Trompeta en Sib", "Clarinete en La", "", "x" * 121])
def test_a_name_that_already_names_an_instrument_or_is_not_valid_is_refused(instruments, name):
    ana, _ = instruments
    response = ana.post("/admin/instruments/flugelhorn.bb/names", json={"name": name})
    assert response.status_code in (409, 422), name


def test_a_new_common_instrument(instruments):
    ana, berta = instruments
    response = ana.post("/admin/instruments", json={
        "label_es": "Dulzaina", "label_en": "Dulzaina", "section": "woodwinds", "family": "dulzaina",
        "transposition": None, "sound": "oboe", "rehearsal_group": "double_reeds", "names": ["Dulzaina", "Gaita castellana"]})
    assert response.status_code == 201, response.text
    canonical_id = response.json()["canonical_id"]
    assert match_instrument_name("Gaita castellana 2").identity.canonical_id == canonical_id
    assert canonical_id in [item["canonical_id"] for item in berta.get("/instruments/catalog").json()["instruments"]]
    assert ana.post("/admin/instruments", json={
        "label_es": "Otra", "label_en": "Other", "section": "woodwinds", "family": "x", "transposition": None,
        "sound": "oboe", "rehearsal_group": "double_reeds", "names": ["Dulzaina"]}).status_code == 409

    changed = ana.patch("/admin/instruments/" + canonical_id, json={"label_es": "Dulzaina castellana"})
    assert changed.status_code == 200 and changed.json()["label_es"] == "Dulzaina castellana"


@pytest.mark.parametrize("field, value", [("section", "kazoo"), ("transposition", "H"), ("sound", "theremin"),
                                          ("rehearsal_group", "solistas"), ("label_es", "")])
def test_a_new_instrument_takes_only_known_values(instruments, field, value):
    ana, _ = instruments
    body = {"label_es": "Dulzaina", "label_en": "Dulzaina", "section": "woodwinds", "family": "dulzaina",
            "transposition": None, "sound": "oboe", "rehearsal_group": "double_reeds", "names": ["Dulzaina"]}
    body[field] = value
    assert ana.post("/admin/instruments", json=body).status_code == 422


def test_only_the_administration_edits_the_catalog(instruments):
    ana, berta = instruments
    assert berta.get("/admin/instruments").status_code == 403
    assert berta.post("/admin/instruments/flugelhorn.bb/names", json={"name": "Fiscornio"}).status_code == 403
    assert berta.delete("/admin/instruments/names/1").status_code == 403
    assert ana.post("/admin/instruments/no.existe/names", json={"name": "Fiscornio"}).status_code == 404
    assert ana.delete("/admin/instruments/names/999999").status_code == 404
    del ana.headers["X-CSRF-Token"]
    assert ana.post("/admin/instruments/flugelhorn.bb/names", json={"name": "Fiscornio"}).status_code == 403
