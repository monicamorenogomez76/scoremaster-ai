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
    [campaign] = signed.get("/evaluations").json()["owned"]
    assert campaign["status"] == "draft" and campaign["passages"] >= 5

    assert seed_demo_content(TestClient(app), "demo@banda.org", "una contraseña larga", TODAY) == "exists"
    assert len(signed.get("/works").json()["works"]) == 3 and len(signed.get("/concerts").json()["concerts"]) == 1


def test_the_demo_works_are_the_generated_ones_with_their_licence():
    files = sorted(path.name for path in DEMO_DIR.glob("*.musicxml"))
    assert files == ["andante-y-danza.musicxml", "coral-para-principiantes.musicxml", "marcha-de-la-plaza.musicxml"]
    assert "CC0" in (DEMO_DIR / "LICENSES.md").read_text()


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
