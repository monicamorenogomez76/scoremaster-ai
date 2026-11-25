"""The rights of access, portability and erasure (2026-11-25): an account downloads everything it keeps and can be
deleted with all of it, and the security log does not keep addresses for ever."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app import auth_routes
from backend.app.dependencies import get_account_repository, get_analysis_repository, get_library_repository, get_personal_data
from backend.app.main import app
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.library_repository import PostgresLibraryRepository
from backend.infrastructure.personal_data import PostgresPersonalData
from backend.test.test_library_api import SCORES, analyze

pytestmark = pytest.mark.real_auth
PASSWORD = "una contraseña larga"


@pytest.fixture
def engine(postgres_engine):
    auth_routes.LIMITER.reset()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    app.dependency_overrides[get_analysis_repository] = lambda: PostgresAnalysisRepository(postgres_engine)
    app.dependency_overrides[get_library_repository] = lambda: PostgresLibraryRepository(postgres_engine)
    app.dependency_overrides[get_personal_data] = lambda: PostgresPersonalData(postgres_engine)
    try:
        yield postgres_engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def account(name):
    client = TestClient(app)
    client.headers["X-CSRF-Token"] = client.post("/auth/register", json={
        "email": name + "@banda.org", "password": PASSWORD, "display_name": name}).json()["csrf_token"]
    return client


def count(engine, table, where="true", **values):
    with engine.connect() as connection:
        return connection.execute(text(f"select count(*) from {table} where {where}"), values).scalar()


def run(engine, sql, **values):
    with engine.begin() as connection:
        return connection.execute(text(sql), values)


def campaign(engine, owner, *emails):
    run(engine, "insert into evaluation_campaigns (id, owner_id, title, instructions, status) select gen_random_uuid(), id, 'Campaña', '', 'open' from users where email = :owner", owner=owner)
    for email in emails:
        run(engine, "insert into evaluation_invitations (id, campaign_id, email, experience_level, main_instrument) "
                    "select gen_random_uuid(), id, :email, 'professional', 'Oboe' from evaluation_campaigns", email=email)


def delete_account(client, body):
    return client.request("DELETE", "/auth/me", json=body)


def test_an_account_downloads_what_it_keeps_and_nothing_of_the_others(engine):
    ana, berta = account("ana"), account("berta")
    assert analyze(ana).status_code == 200
    assert analyze(berta, "high_density.musicxml").status_code == 200
    campaign(engine, "berta@banda.org", "ana@banda.org", "carla@banda.org")
    response = ana.get("/auth/me/data")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"] and response.headers["cache-control"] == "no-store"
    archive = zipfile.ZipFile(BytesIO(response.content))
    data = json.loads(archive.read("datos.json"))
    assert data["account"][0]["email"] == "ana@banda.org"
    assert [work["file_name"] for work in data["works"]] == ["high_register.musicxml"]
    assert data["invitations"][0]["main_instrument"] == "Oboe"
    assert {event["event"] for event in data["security_log"]} >= {"registered"}
    scores = [name for name in archive.namelist() if name.startswith("partituras/")]
    assert len(scores) == 1 and archive.read(scores[0]) == (SCORES / "high_register.musicxml").read_bytes()
    everything = archive.read("datos.json").decode()
    for secret in ("berta@", "carla@", "password_hash", "token_hash", "csrf"):
        assert secret not in everything


def test_the_data_needs_a_session(engine):
    assert TestClient(app).get("/auth/me/data").status_code == 401
    assert delete_account(TestClient(app), {"password": PASSWORD}).status_code == 401


def test_deleting_the_account_deletes_everything_it_keeps(engine):
    ana, berta = account("ana"), account("berta")
    for client in (ana, berta):
        assert analyze(client).status_code == 200
    assert analyze(ana, "high_density.musicxml").status_code == 200
    keys = dict(run(engine, "select file_name, source_sha256 from works").fetchall())
    for key in keys.values():
        run(engine, "insert into prepared_works (source_sha256, kind, version, data) values (:key, 'score', 'v', ''::bytea)", key=key)
    campaign(engine, "berta@banda.org", "ana@banda.org", "carla@banda.org")
    response = delete_account(ana, {"password": PASSWORD})
    assert response.status_code == 204
    assert 'scoremaster_session=""' in response.headers["set-cookie"]
    assert ana.get("/auth/me").status_code == 401
    assert count(engine, "users", "email = 'ana@banda.org'") == 0 and count(engine, "users") == 1
    assert count(engine, "works") == 1 and count(engine, "audit_events", "user_id is null") == 0
    assert [row.email for row in run(engine, "select email from evaluation_invitations")] == ["carla@banda.org"]
    assert [row.source_sha256 for row in run(engine, "select source_sha256 from prepared_works")] == [keys["high_register.musicxml"]], \
        "a work another account also has stays prepared"
    assert TestClient(app).post("/auth/login", json={"email": "ana@banda.org", "password": PASSWORD}).status_code == 401


def test_the_password_is_asked_and_its_attempts_are_limited(engine):
    ana = account("ana")
    for _ in range(5):
        response = delete_account(ana, {"password": "otra"})
        assert response.status_code == 403 and response.json()["detail"] == "La contraseña no es correcta."
    assert delete_account(ana, {"password": PASSWORD}).status_code == 429
    assert count(engine, "users") == 1


def test_it_needs_the_csrf_token(engine):
    ana = account("ana")
    del ana.headers["X-CSRF-Token"]
    assert delete_account(ana, {"password": PASSWORD}).status_code == 403
    assert count(engine, "users") == 1


def test_an_account_without_password_confirms_its_email(engine):
    ana = account("ana")
    run(engine, "update users set password_hash = null")
    assert delete_account(ana, {"email": "otra@banda.org"}).status_code == 403
    assert delete_account(ana, {"email": " Ana@Banda.org "}).status_code == 204


def test_the_demo_account_is_not_deleted(engine, monkeypatch):
    monkeypatch.setenv("DEMO_USER_EMAIL", "ana@banda.org")
    assert delete_account(account("ana"), {"password": PASSWORD}).status_code == 403
    assert count(engine, "users") == 1


def test_an_email_not_confirmed_gives_no_access_to_the_invitations(engine, monkeypatch):
    """Anyone could register a musician's email: without confirming it, their ratings are neither given nor deleted."""
    ana = account("ana")
    account("berta")
    campaign(engine, "berta@banda.org", "ana@banda.org")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    data = json.loads(zipfile.ZipFile(BytesIO(ana.get("/auth/me/data").content)).read("datos.json"))
    assert data["invitations"] == []
    assert delete_account(ana, {"password": PASSWORD}).status_code == 204
    assert count(engine, "evaluation_invitations") == 1


def test_the_security_log_forgets_what_is_older_than_a_year(engine):
    account("ana")
    old = datetime.now(timezone.utc) - timedelta(days=366)
    run(engine, "insert into audit_events (user_id, event, ip, created_at) values (null, 'login_failed', '10.0.0.1', :old)", old=old)
    before = count(engine, "audit_events")
    assert PostgresPersonalData(engine).forget_old_events() == 1
    assert count(engine, "audit_events") == before - 1
