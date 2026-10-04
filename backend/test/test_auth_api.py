"""Authentication over HTTP (plan phase 1): session cookie, CSRF token, protected endpoints, Google opt-in."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backend.app import auth_routes
from backend.app.dependencies import get_account_repository, get_analysis_repository
from backend.app.main import app
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository

pytestmark = pytest.mark.real_auth
PASSWORD = "correct horse battery"
SCORE = Path(__file__).resolve().parents[2] / "test-scores" / "high_register.musicxml"


@pytest.fixture
def client(postgres_engine, monkeypatch):
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    auth_routes.LIMITER.reset()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    app.dependency_overrides[get_analysis_repository] = lambda: PostgresAnalysisRepository(postgres_engine)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def register(client, email="directora@banda.org"):
    return client.post("/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Directora"})


def analyze(client, headers=None):
    with SCORE.open("rb") as musicxml:
        return client.post("/analyze", files={"file": ("high_register.musicxml", musicxml, "application/xml")},
                           headers=headers or {})


def test_register_signs_in_with_an_httponly_session_cookie(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json()["user"] == {"email": "directora@banda.org", "display_name": "Directora"}
    cookie = response.headers["set-cookie"]
    assert "scoremaster_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Secure" not in cookie   # local HTTP; production sets it
    assert client.get("/auth/me").json()["user"]["email"] == "directora@banda.org"


def test_login_failures_do_not_reveal_whether_the_email_exists(client):
    register(client)
    client.cookies.clear()
    unknown = client.post("/auth/login", json={"email": "nadie@banda.org", "password": PASSWORD})
    wrong = client.post("/auth/login", json={"email": "directora@banda.org", "password": "no es esta"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert client.get("/auth/me").status_code == 401


def test_too_many_failures_answer_429(client):
    register(client)
    client.cookies.clear()
    for _ in range(5):
        client.post("/auth/login", json={"email": "directora@banda.org", "password": "no es esta"})
    assert client.post("/auth/login", json={"email": "directora@banda.org", "password": PASSWORD}).status_code == 429


def test_protected_endpoints_need_a_session_and_the_csrf_token(client):
    assert analyze(client).status_code == 401

    csrf = register(client).json()["csrf_token"]
    assert analyze(client).status_code == 403
    assert analyze(client, {"X-CSRF-Token": "otro"}).status_code == 403
    assert analyze(client, {"X-CSRF-Token": csrf}).status_code == 200


def test_requests_from_another_origin_are_refused(client):
    response = client.post("/auth/register", json={"email": "a@b.org", "password": PASSWORD, "display_name": "A"},
                           headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_logout_closes_the_session(client):
    csrf = register(client).json()["csrf_token"]

    assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_google_is_disabled_without_credentials(client):
    assert client.get("/auth/config").json()["google_enabled"] is False
    assert client.get("/auth/google/start", follow_redirects=False).status_code == 404


def test_google_sign_in_uses_state_and_pkce(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    start = client.get("/auth/google/start", follow_redirects=False)

    assert start.status_code == 302
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert urlparse(start.headers["location"]).netloc == "accounts.google.com"
    assert query["code_challenge_method"] == ["S256"] and query["state"][0]

    monkeypatch.setattr(auth_routes, "exchange_google_code", lambda code, verifier, redirect_uri: {
        "sub": "google-1", "email": "nueva@banda.org", "email_verified": True, "name": "Nueva"})
    assert client.get("/auth/google/callback", params={"code": "c", "state": "falso"},
                      follow_redirects=False).status_code == 400
    callback = client.get("/auth/google/callback", params={"code": "c", "state": query["state"][0]},
                          follow_redirects=False)
    assert callback.status_code == 302 and callback.headers["location"] == "/"
    assert client.get("/auth/me").json()["user"]["email"] == "nueva@banda.org"


def test_responses_carry_security_headers(client):
    headers = client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com" in headers["content-security-policy"]
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_uploads_are_limited_before_parsing(client):
    csrf = register(client).json()["csrf_token"]
    huge = b"<score-partwise>" + b" " * (8 * 1024 * 1024)
    response = client.post("/analyze", files={"file": ("big.musicxml", huge, "application/xml")},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 413
    entity = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><score-partwise/>'
    response = client.post("/analyze", files={"file": ("entity.musicxml", entity, "application/xml")},
                           headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400
