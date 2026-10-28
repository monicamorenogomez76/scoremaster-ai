"""What an account confirms is learnt (2026-10-28): the instrument chosen for a part name is remembered for that
account, so the next work with «Fiscornio 1» or «Fiscornio 3» comes recognised. An instrument the catalog does not
have is created for the account with its name, family and key. Nothing an account learns reaches another one."""
import json
from pathlib import Path

import pytest

from backend.app.dependencies import get_instrument_repository, get_instrument_store
from backend.app.main import app
from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
from backend.test.test_library_api import clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth
SCORE = (Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml").read_text(encoding="utf-8")
DULZAINA = {"name": "Dulzaina 1", "label_es": "Dulzaina", "family": "dulzaina", "section": "woodwinds",
            "transposition": None, "sound": "oboe", "rehearsal_group": "double_reeds"}


@pytest.fixture
def accounts(clients, postgres_engine):
    app.dependency_overrides[get_instrument_repository] = lambda: PostgresInstrumentRepository(postgres_engine)
    app.dependency_overrides[get_instrument_store] = lambda: PostgresInstrumentRepository(postgres_engine)
    return clients


def analyze(client, part_name, overrides=None, title="Obra"):
    content = SCORE.replace("<part-name>Clarinet</part-name>", "<part-name>{}</part-name>".format(part_name))
    content = content.replace("<score-partwise version=\"4.0\">", "<score-partwise version=\"4.0\"><!-- {} -->".format(title))
    response = client.post("/analyze", files={"file": (title + ".musicxml", content.encode(), "application/xml")},
                           data={"instrument_overrides": json.dumps(overrides or {})})
    assert response.status_code == 200, response.text
    return response.json()


def identity_of(result):
    [instrument] = result["instruments"]
    return instrument["canonical_id"]


def test_a_confirmed_name_is_recognised_in_the_next_works_of_the_account(accounts):
    ana, berta = accounts
    assert identity_of(analyze(ana, "Fiscornio 1")) is None
    assert identity_of(analyze(ana, "Fiscornio 1", {"Fiscornio 1": "flugelhorn.bb"})) == "flugelhorn.bb"

    later = analyze(ana, "Fiscornio 3", title="Otra obra")
    assert identity_of(later) == "flugelhorn.bb", "learnt without the part number"
    assert later["band_fit"]["unconfirmed"] == []
    assert identity_of(analyze(berta, "Fiscornio 3", title="Otra obra")) is None, "another account learns nothing"


def test_a_name_the_catalog_knows_is_never_changed_by_what_an_account_learnt(accounts):
    ana, _ = accounts
    analyze(ana, "Trompeta 1", {"Trompeta 1": "flugelhorn.bb"})
    assert identity_of(analyze(ana, "Trompeta 2", title="Otra")) == "trumpet.bb"


def test_an_instrument_the_catalog_does_not_have_is_created_for_the_account(accounts):
    ana, berta = accounts
    created = ana.post("/instruments", json=DULZAINA)
    assert created.status_code == 201, created.text
    instrument = created.json()
    assert instrument["canonical_id"].startswith("own.") and instrument["label_es"] == "Dulzaina"
    assert instrument["canonical_id"] in [item["canonical_id"] for item in ana.get("/instruments/catalog").json()["instruments"]]
    assert instrument["canonical_id"] not in [item["canonical_id"] for item in berta.get("/instruments/catalog").json()["instruments"]]

    result = analyze(ana, "Dulzaina 2", title="Con dulzaina")
    assert identity_of(result) == instrument["canonical_id"], "its name is learnt when it is created"
    [requirement] = result["band_fit"]["requirements"]
    assert (requirement["label_es"], requirement["required"]) == ("Dulzaina", 1)

    assert berta.post("/analyze", files={"file": ("o.musicxml", SCORE.encode(), "application/xml")},
                      data={"instrument_overrides": json.dumps({"Clarinet": instrument["canonical_id"]})}).status_code == 400


@pytest.mark.parametrize("field, value", [("section", "kazoo"), ("transposition", "H"), ("sound", "theremin"),
                                          ("rehearsal_group", "solistas"), ("label_es", ""), ("name", ""), ("family", "")])
def test_a_new_instrument_takes_only_known_values(accounts, field, value):
    ana, _ = accounts
    assert ana.post("/instruments", json=dict(DULZAINA, **{field: value})).status_code == 422


def test_creating_an_instrument_needs_the_csrf_token(accounts):
    ana, _ = accounts
    del ana.headers["X-CSRF-Token"]
    assert ana.post("/instruments", json=DULZAINA).status_code == 403
