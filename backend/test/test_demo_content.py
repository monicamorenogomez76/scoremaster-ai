"""The demo account is ready for the examiners and the video (PR 4 of the closing plan, 2026-10-14): three
band works already analysed, a band, a concert with its series of rehearsals and a draft campaign, created
through the real API so they pass the same validation as the director's own. Running it again adds nothing."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app.demo_content import DEMO_DIR, seed_demo_content
from backend.app.main import app
from backend.test.test_library_api import clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth
TODAY = date(2026, 10, 14)


def test_the_demo_account_gets_works_band_concert_and_campaign_once(clients, monkeypatch):
    monkeypatch.setenv("PLAYBACK_WARMUP", "0")
    client = TestClient(app)
    client.post("/auth/register", json={"email": "demo@banda.org", "password": "una contraseña larga",
                                        "display_name": "Usuario demo"})
    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "created"

    signed = TestClient(app)
    signed.headers["X-CSRF-Token"] = signed.post("/auth/login", json={"email": "demo@banda.org",
                                                                      "password": "una contraseña larga"}).json()["csrf_token"]
    works = signed.get("/works").json()["works"]
    assert sorted(work["title"] for work in works) == ["Andante y danza", "Coral para principiantes", "Marcha de la plaza"]
    assert all(work["summary"]["grade"] for work in works)
    assert sorted(work["title"] for work in works if work["preparation_status"] == "preparing") == ["Andante y danza", "Marcha de la plaza"]
    assert signed.get("/works/priorities").json()["priorities"], "the summary shows their critical passages"
    [band] = signed.get("/bands").json()["bands"]
    assert band["name"] == "Banda de demostración" and band["active"] and band["profile"]["clarinet.bb"] >= 2
    [concert] = signed.get("/concerts").json()["concerts"]
    assert [work["title"] for work in concert["works"]] == ["Marcha de la plaza", "Andante y danza"]
    series = [item for item in signed.get("/rehearsals").json()["rehearsals"] if item["concert_id"] == concert["id"]]
    assert len(series) >= 4 and series[-1]["phase"] == "general"
    assert all(block["title"] and block["minutes"] > 0 for item in series for block in item["blocks"])
    # 2026-10-14: the demo is not an administrator (its password is in the README), so it never sees the
    # results of a campaign; its example campaign is open and it is invited, to show the musician's side.
    listing = signed.get("/evaluations").json()
    assert listing["owned"] == [] and listing["can_manage"] is False
    [campaign] = listing["invited"]
    assert campaign["status"] == "open" and campaign["passages"] >= 5
    view = signed.get("/evaluations/" + campaign["id"]).json()
    assert view["role"] == "evaluator" and all("snapshot" not in item for item in view["passages"])

    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "exists"
    assert len(signed.get("/works").json()["works"]) == 3 and len(signed.get("/concerts").json()["concerts"]) == 1


def test_the_demo_works_are_the_generated_ones_with_their_licence():
    files = sorted(path.name for path in DEMO_DIR.glob("*.musicxml"))
    assert files == ["andante-y-danza.musicxml", "coral-para-principiantes.musicxml", "marcha-de-la-plaza.musicxml"]
    assert "CC0" in (DEMO_DIR / "LICENSES.md").read_text()


@pytest.mark.parametrize("filename, concert_fifths", [
    ("marcha-de-la-plaza.musicxml", -2), ("andante-y-danza.musicxml", -3), ("coral-para-principiantes.musicxml", -3)])
def test_each_part_has_the_written_key_of_its_transposition(filename, concert_fifths):
    """2026-10-14: one KeySignature object shared by every part was transposed once per transposing
    instrument (fifths 11-13); the notation engine refused it («bad key signature») in Render."""
    import xml.etree.ElementTree as ET
    root = ET.parse(DEMO_DIR / filename).getroot()
    names = {part.get("id"): part.findtext("part-name") for part in root.iter("score-part")}
    written = {}
    for part in root.iter("part"):
        if names[part.get("id")].endswith("Drum"):
            continue   # percussion is written without a key signature
        fifths = int(part.find("measure/attributes/key/fifths").text)
        chromatic = part.findtext("measure/attributes/transpose/chromatic")
        # Written key = concert key raised by the interval the instrument sounds below (7 fifths per semitone, mod 12).
        expected = concert_fifths if chromatic is None else (concert_fifths - 7 * int(chromatic) + 6) % 12 - 6
        written[names[part.get("id")]] = fifths
        assert -7 <= fifths <= 7 and fifths == expected, names[part.get("id")]
    assert written["Flute"] == concert_fifths and written["Clarinet in Bb 1"] == concert_fifths + 2


def test_without_the_account_nothing_is_seeded(clients):
    assert seed_demo_content(TestClient(app), "nadie@banda.org", "una contraseña larga", TODAY) == "skipped"


def test_the_seed_works_with_the_secure_cookies_of_production(clients, monkeypatch):
    """In production the session cookie is Secure: the seed talks to the app over https."""
    from backend.app import seed_demo
    monkeypatch.setenv("APP_ENV", "production")
    client = TestClient(app)
    client.post("/auth/register", json={"email": "demo2@banda.org", "password": "una contraseña larga",
                                        "display_name": "Usuario demo"})
    from backend.app import demo_content
    calls = []
    monkeypatch.setattr(demo_content, "seed_demo_content",
                        lambda client, email, password, today: calls.append(str(client.base_url)) or "created")
    assert seed_demo.seed_content("demo2@banda.org", "una contraseña larga") == "creado"
    assert calls == ["https://testserver"]


def test_the_demo_works_are_exactly_what_the_generator_writes(tmp_path):
    """The files in demo/ never drift from scripts/generate_demo_scores.py (only music21's encoding date varies)."""
    import re
    import subprocess
    import sys
    root = DEMO_DIR.parent
    subprocess.run([sys.executable, str(root / "scripts" / "generate_demo_scores.py"), str(tmp_path)], check=True,
                   capture_output=True, cwd=root)
    without_date = lambda text: re.sub(r"<encoding-date>[^<]*</encoding-date>", "", text)
    for kept in DEMO_DIR.glob("*.musicxml"):
        assert without_date((tmp_path / kept.name).read_text()) == without_date(kept.read_text()), kept.name
    # The compressed work to upload: its MusicXML inside the zip (the zip's own dates vary).
    from backend.parsers.musicxml_parser import extract_musicxml
    upload = "para-subir/pasodoble-de-las-fiestas.mxl"
    inside = lambda path: without_date(extract_musicxml(path.read_bytes()).decode())
    assert inside(tmp_path / upload) == inside(DEMO_DIR / upload)


def _signed(email="demo@banda.org"):
    signed = TestClient(app)
    signed.headers["X-CSRF-Token"] = signed.post("/auth/login", json={"email": email, "password": "una contraseña larga"}).json()["csrf_token"]
    return signed


def _seeded_demo():
    TestClient(app).post("/auth/register", json={"email": "demo@banda.org", "password": "una contraseña larga",
                                                 "display_name": "Usuario demo"})
    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "created"


def _current_sources():
    import hashlib
    return frozenset(hashlib.sha256(path.read_bytes()).hexdigest() for path in DEMO_DIR.glob("*.musicxml"))


def test_a_demo_made_with_earlier_works_is_made_again_with_the_current_ones(clients, postgres_engine, monkeypatch):
    """2026-10-14: the works were rewritten with real harmony; Render's demo account kept the old ones,
    whose analyses, concert and campaign no longer match. Only the demo's own earlier works trigger it."""
    from backend.app import demo_content
    monkeypatch.setenv("PLAYBACK_WARMUP", "0")
    _seeded_demo()
    assert demo_content.reset_outdated_demo(postgres_engine, "demo@banda.org") is False, "the current works stay"
    monkeypatch.setattr(demo_content, "OUTDATED_SOURCES", _current_sources())
    assert demo_content.reset_outdated_demo(postgres_engine, "demo@banda.org") is True
    signed = _signed()
    assert signed.get("/works").json()["works"] == [] and signed.get("/concerts").json()["concerts"] == []
    assert signed.get("/evaluations").json()["invited"] == [] and signed.get("/bands").json()["bands"] == []
    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "created"
    assert len(signed.get("/works").json()["works"]) == 3 and len(signed.get("/evaluations").json()["invited"]) == 1


def test_a_demo_account_with_other_works_is_left_alone(clients, postgres_engine, monkeypatch):
    from backend.app import demo_content
    from backend.test.test_library_api import analyze
    monkeypatch.setenv("PLAYBACK_WARMUP", "0")
    _seeded_demo()
    signed = _signed()
    analyze(signed)
    monkeypatch.setattr(demo_content, "OUTDATED_SOURCES", _current_sources())
    assert demo_content.reset_outdated_demo(postgres_engine, "demo@banda.org") is False
    assert len(signed.get("/works").json()["works"]) == 4


def test_the_published_earlier_works_count_as_outdated():
    from backend.app.demo_content import OUTDATED_SOURCES
    assert len(OUTDATED_SOURCES) == 6 and not (_current_sources() & OUTDATED_SOURCES)


def test_the_draft_campaign_of_an_existing_demo_is_opened_to_the_demo(clients, monkeypatch):
    """Render's demo account was seeded with a draft campaign it owns; once it is no longer an administrator,
    the next start opens it and invites the demo, so the demo still has something to rate."""
    from backend.app.demo_content import DEMO_CAMPAIGN
    monkeypatch.setenv("PLAYBACK_WARMUP", "0")
    _seeded_demo()
    signed = _signed()
    monkeypatch.setenv("ADMIN_EMAILS", "demo@banda.org")
    work = signed.get("/works").json()["works"][0]["id"]
    draft = signed.post("/evaluations", json={"title": DEMO_CAMPAIGN, "work_ids": [work], "size": 10}).json()
    assert draft["status"] == "draft"
    monkeypatch.delenv("ADMIN_EMAILS")

    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "exists"
    invited = {item["id"]: item["status"] for item in signed.get("/evaluations").json()["invited"]}
    assert invited[draft["id"]] == "open" and len(invited) == 2
    import os
    assert "ADMIN_EMAILS" not in os.environ, "the seed gives the demo no lasting rights"
