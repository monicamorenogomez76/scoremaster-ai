"""Who answers for the personal data of an installation (2026-11-25): in its environment, never in the repository."""
from fastapi.testclient import TestClient

from backend.app.main import app


def test_the_controller_and_its_contact_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("PRIVACY_CONTROLLER", "Banda de prueba")
    monkeypatch.setenv("PRIVACY_EMAIL", "datos@banda.test")
    assert TestClient(app).get("/auth/config").json()["privacy"] == {"controller": "Banda de prueba", "email": "datos@banda.test"}


def test_without_them_the_policy_says_so(monkeypatch):
    monkeypatch.delenv("PRIVACY_CONTROLLER", raising=False)
    monkeypatch.setenv("PRIVACY_EMAIL", "")
    assert TestClient(app).get("/auth/config").json()["privacy"] == {"controller": None, "email": None}


def test_the_password_of_the_demo_is_told_to_be_in_the_readme_only_where_it_is(monkeypatch):
    """The README gives the one of the local demo; the published one has another (2026-11-25)."""
    monkeypatch.setenv("DEMO_USER_EMAIL", "demo@scoremaster.local")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert TestClient(app).get("/auth/config").json()["demo_password_in_readme"] is True
    monkeypatch.setenv("APP_ENV", "production")
    config = TestClient(app).get("/auth/config").json()
    assert config["demo_password_in_readme"] is False and config["demo_email"] == "demo@scoremaster.local"
