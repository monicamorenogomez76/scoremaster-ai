"""Deterministic instrument resolution from part name and MusicXML metadata (step 08)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_analysis_repository
from backend.app.main import app
from backend.domain.instrument_resolver import (
    AUTO_ACCEPT_CONFIDENCE,
    CONFLICT,
    RESOLVED,
    REVIEW,
    REVIEW_CONFIDENCE,
    UNKNOWN,
    resolve_part,
)
from backend.domain.models import PartMetadata, ScorePart


def part(name, instruments=(), display=None, staff=None):
    metadata = PartMetadata(part_id="P1", part_name=name, instrument_names=tuple(instruments), staff_number=staff)
    return ScorePart(display or name or "Part 1", (), metadata)


def test_name_and_metadata_that_agree_resolve_with_high_confidence():
    resolution = resolve_part(part("B♭ Clarinet 1", ["B♭ Clarinet"]))

    assert resolution.identity.canonical_id == "clarinet.bb"
    assert resolution.status == RESOLVED
    assert resolution.source == "MUSICXML"
    assert resolution.confidence >= 0.95
    assert resolution.part_numbers == (1,)
    assert resolution.evidence == ("part-name 'B♭ Clarinet 1' → clarinet.bb", "instrument-name 'B♭ Clarinet' → clarinet.bb")


def test_explicit_part_name_alone_is_accepted():
    resolution = resolve_part(part("Piano", ["Acoustic Grand Piano"]))

    assert resolution.identity.canonical_id == "piano"
    assert resolution.status == RESOLVED
    assert resolution.source == "ALIAS"
    assert resolution.confidence >= AUTO_ACCEPT_CONFIDENCE


@pytest.mark.parametrize("name", ["Voice", "Trombone 3 & Bass Trombone"])
def test_metadata_alone_is_proposed_for_review(name):
    instrument = "Trombone" if name.startswith("Trombone") else "Clarinet"
    resolution = resolve_part(part(name, [instrument]))

    assert resolution.identity is not None
    assert resolution.status == REVIEW
    assert resolution.source == "MUSICXML"
    assert REVIEW_CONFIDENCE <= resolution.confidence < AUTO_ACCEPT_CONFIDENCE


def test_disagreement_is_never_resolved_automatically():
    resolution = resolve_part(part("Flute", ["Piccolo"]))

    assert resolution.identity is None
    assert resolution.status == CONFLICT
    assert resolution.confidence == 0
    assert [candidate.canonical_id for candidate in resolution.candidates] == ["flute", "piccolo"]


def test_generic_names_without_usable_metadata_stay_unknown():
    resolution = resolve_part(part("Voice", ["Voice Oohs"], display="Voice 3"))

    assert resolution.identity is None
    assert resolution.status == UNKNOWN
    assert resolution.source == "UNKNOWN"
    assert resolution.confidence == 0
    assert resolution.part == "Voice 3"


def test_percussion_kit_sounds_are_not_evidence_of_one_instrument():
    kit = ["Acoustic Bass Drum", "Tambourine", "Triangle", "Crash Cymbal 1"]

    assert resolve_part(part("Voice", kit)).status == UNKNOWN
    snare = resolve_part(part("Concert Snare Drum", ["Side Stick", "Acoustic Snare"]))
    assert snare.identity.canonical_id == "snare_drum"
    assert snare.status == RESOLVED


def test_one_recognisable_instrument_name_among_unknown_ones_counts_once():
    resolution = resolve_part(part("Cymbal", ["Crash Cymbal 2", "Instrument 60"]))

    assert resolution.identity.canonical_id == "crash_cymbals"
    assert resolution.status == REVIEW


def test_staff_of_a_split_part_becomes_its_part_number():
    assert resolve_part(part("Horn in F", ["Horn in F"], display="Horn in F 2", staff=2)).part_numbers == (2,)


def test_parts_built_without_metadata_fall_back_to_their_name():
    resolution = resolve_part(ScorePart("Clarinet", ()))

    assert resolution.identity.canonical_id == "clarinet.bb"
    assert resolution.status == RESOLVED


def test_resolution_serializes_for_the_api():
    payload = resolve_part(part("Bass Clarinet", ["Bass Clarinet"])).as_dict()

    assert payload["part"] == "Bass Clarinet"
    assert payload["canonical_id"] == "clarinet.bass"
    assert payload["label_es"] == "Clarinete bajo"
    assert payload["section"] == "woodwinds"
    assert payload["transposition"] == "Bb"
    assert payload["status"] == "resolved"
    assert payload["candidates"] == []
    json.dumps(payload)


def test_analyze_reports_resolved_instruments():
    class Repository:
        def save(self, record):
            return record.analysis_id
    app.dependency_overrides[get_analysis_repository] = Repository
    try:
        score_path = Path(__file__).resolve().parents[2] / "test-scores" / "high_density.musicxml"
        with score_path.open("rb") as musicxml:
            response = TestClient(app).post("/analyze", files={"file": ("high_density.musicxml", musicxml, "application/xml")})
    finally:
        app.dependency_overrides.pop(get_analysis_repository, None)

    assert response.status_code == 200
    [instrument] = response.json()["instruments"]
    assert instrument["part"] == "Clarinet"
    assert instrument["canonical_id"] == "clarinet.bb"
    assert instrument["status"] == "resolved"
