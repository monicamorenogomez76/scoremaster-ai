"""Human confirmation of instruments through the API (step 09)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_analysis_repository
from backend.app.main import app

SCORE = Path(__file__).resolve().parents[2] / "test-scores" / "high_density.musicxml"


@pytest.fixture
def saved():
    records = []

    class Repository:
        def save(self, record):
            records.append(record)
            return record.analysis_id
    app.dependency_overrides[get_analysis_repository] = Repository
    yield records
    app.dependency_overrides.pop(get_analysis_repository, None)


def analyze(**data):
    with SCORE.open("rb") as musicxml:
        return TestClient(app).post("/analyze", files={"file": ("high_density.musicxml", musicxml, "application/xml")},
                                    data=data)


def test_a_confirmed_identity_is_used_by_the_analysis_and_bandfit(saved):
    response = analyze(instrument_overrides=json.dumps({"Clarinet": "clarinet.eb"}),
                       band_profile=json.dumps({"clarinet.eb": 1}))

    assert response.status_code == 200
    [instrument] = response.json()["instruments"]
    assert (instrument["canonical_id"], instrument["source"]) == ("clarinet.eb", "USER")
    assert response.json()["band_fit"]["requirements"][0]["key"] == "clarinet.eb"
    assert saved[0].configuration["instrument_overrides"] == {"Clarinet": "clarinet.eb"}


@pytest.mark.parametrize("overrides", ['{"Clarinet": "kazoo"}', "[1]", "not json", '{"Clarinet": 3}'])
def test_invalid_confirmations_are_rejected(saved, overrides):
    assert analyze(instrument_overrides=overrides).status_code == 400


def test_a_confirmation_for_a_part_that_is_not_in_the_score_is_ignored(saved):
    response = analyze(instrument_overrides=json.dumps({"Oboe 7": "oboe"}))

    assert response.status_code == 200
    assert response.json()["instruments"][0]["source"] != "USER"


def test_the_catalog_lists_identities_for_the_confirmation_menu():
    response = TestClient(app).get("/instruments/catalog")

    assert response.status_code == 200
    entries = response.json()["instruments"]
    # With its English name for the interface in English (2026-10-30).
    assert {"canonical_id": "clarinet.bb", "label_es": "Clarinete en Si bemol", "label_en": "B♭ Clarinet", "section": "woodwinds"} in entries
    assert response.json()["percussion_key"] == "percussion"


@pytest.mark.parametrize("profile", ['{"clarinet.bb": "muchos"}', '{"clarinet.bb": -1}', '{"clarinet.bb": 100000}', "[]"])
def test_band_profiles_must_be_musician_counts(saved, profile):
    assert analyze(band_profile=profile).status_code == 400
