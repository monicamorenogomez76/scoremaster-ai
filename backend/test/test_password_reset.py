"""Password recovery by email (2026-10-29): a one-time link that expires in 30 minutes. The answer never says whether
an account has that email; the database keeps only the link's SHA-256; using it sets the new password, closes every
other session and signs in. Without a mail service the recovery is off in production; in development the link is
written to the server's log."""
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import auth_routes
from backend.app.dependencies import get_account_repository, get_mailer
from backend.app.main import app
from backend.application.auth import RESET_MINUTES, AuthService, InvalidRegistration, InvalidResetLink, LoginLimiter
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.infrastructure.mailer import BrevoMailer, LogMailer, mailer_from_env
from backend.test.account_fakes import InMemoryAccounts
from backend.test.test_auth_service import PASSWORD, Clock

NEW_PASSWORD = "otra contraseña larga"


@pytest.fixture
def service():
    clock = Clock()
    accounts = InMemoryAccounts()
    auth = AuthService(accounts, clock=clock, limiter=LoginLimiter(clock=clock), reset_limiter=LoginLimiter(3, clock=clock))
    auth.clock_handle, auth.accounts = clock, accounts
    auth.register("directora@banda.org", PASSWORD, "Directora", ip="10.0.0.1")
    return auth


def test_a_reset_link_sets_the_new_password_closes_the_other_sessions_and_signs_in(service):
    user, token = service.request_password_reset("Directora@Banda.org ", ip="10.0.0.1")
    assert user.email == "directora@banda.org" and len(token) >= 43
    assert token not in str(service.accounts.resets), "only the SHA-256 is stored"

    signed_in = service.reset_password(token, NEW_PASSWORD, ip="10.0.0.1")
    assert signed_in.user.id == user.id
    assert len(service.accounts.sessions) == 1, "the sessions opened with the old password are closed"
    assert service.login("directora@banda.org", NEW_PASSWORD, ip="10.0.0.1")
    with pytest.raises(InvalidResetLink):
        service.reset_password(token, "y otra más todavía", ip="10.0.0.1")
    assert "password_reset" in [event for _, event, _ in service.accounts.events]


def test_a_link_expires_and_only_the_last_one_works(service):
    _, first = service.request_password_reset("directora@banda.org", ip="10.0.0.1")
    _, second = service.request_password_reset("directora@banda.org", ip="10.0.0.1")
    with pytest.raises(InvalidResetLink):
        service.reset_password(first, NEW_PASSWORD, ip="10.0.0.1")
    service.clock_handle.now += timedelta(minutes=RESET_MINUTES + 1)
    with pytest.raises(InvalidResetLink):
        service.reset_password(second, NEW_PASSWORD, ip="10.0.0.1")


def test_a_short_password_keeps_the_link_for_another_try(service):
    _, token = service.request_password_reset("directora@banda.org", ip="10.0.0.1")
    with pytest.raises(InvalidRegistration):
        service.reset_password(token, "corta", ip="10.0.0.1")
    assert service.reset_password(token, NEW_PASSWORD, ip="10.0.0.1")


def test_unknown_emails_and_too_many_requests_send_nothing(service):
    assert service.request_password_reset("nadie@banda.org", ip="10.0.0.1") is None
    assert [service.request_password_reset("directora@banda.org", ip=f"10.0.0.{n}") for n in range(4)][3] is None, \
        "three links an hour per email, whatever the address"


def test_brevo_receives_the_message_with_the_sender_and_the_key_in_its_header():
    sent = {}

    def handler(request):
        sent["request"] = request
        return httpx.Response(201, json={"messageId": "1"})

    mailer = BrevoMailer("clave", "ScoreMaster <avisos@banda.org>", client=httpx.Client(transport=httpx.MockTransport(handler)))
    mailer.send("directora@banda.org", "Asunto", "Texto")
    request = sent["request"]
    assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
    assert request.headers["api-key"] == "clave"
    assert json.loads(request.content) == {"sender": {"name": "ScoreMaster", "email": "avisos@banda.org"},
                                           "to": [{"email": "directora@banda.org"}], "subject": "Asunto",
                                           "textContent": "Texto"}


def test_the_mail_service_comes_from_the_environment(monkeypatch):
    for name in ("BREVO_API_KEY", "MAIL_FROM", "APP_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert isinstance(mailer_from_env(), LogMailer), "in development the link goes to the log"
    monkeypatch.setenv("APP_ENV", "production")
    assert mailer_from_env() is None, "in production without a mail service there is no recovery"
    monkeypatch.setenv("BREVO_API_KEY", "clave")
    monkeypatch.setenv("MAIL_FROM", "avisos@banda.org")
    assert mailer_from_env() is None, "nor without the public address the link points to"
    monkeypatch.setenv("APP_BASE_URL", "https://scoremaster.example")
    assert isinstance(mailer_from_env(), BrevoMailer)


class Outbox:
    def __init__(self):
        self.messages = []

    def send(self, to, subject, text):
        self.messages.append((to, subject, text))


@pytest.fixture
def client(postgres_engine, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://scoremaster.example")
    monkeypatch.setenv("DEMO_USER_EMAIL", "demo@scoremaster.local")
    auth_routes.LIMITER.reset()
    auth_routes.RESET_LIMITER.reset()
    outbox = Outbox()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_account_repository] = lambda: PostgresAccountRepository(postgres_engine)
    app.dependency_overrides[get_mailer] = lambda: outbox
    try:
        test_client = TestClient(app)
        test_client.outbox = outbox
        yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)



def _link(text):
    return next(word for word in text.split() if word.startswith("https://"))


@pytest.mark.real_auth
def test_over_http_the_answer_is_the_same_for_any_email_and_the_link_signs_in(client):
    client.post("/auth/register", json={"email": "directora@banda.org", "password": PASSWORD})
    client.post("/auth/register", json={"email": "demo@scoremaster.local", "password": PASSWORD})
    client.cookies.clear()
    known = client.post("/auth/password/forgot", json={"email": "directora@banda.org"})
    unknown = client.post("/auth/password/forgot", json={"email": "nadie@banda.org"})
    demo = client.post("/auth/password/forgot", json={"email": "demo@scoremaster.local"})
    assert known.status_code == unknown.status_code == demo.status_code == 202
    assert known.json() == unknown.json() == demo.json()
    [(to, subject, text)] = client.outbox.messages
    assert to == "directora@banda.org" and "contraseña" in subject.lower()
    link = _link(text)
    assert link.startswith("https://scoremaster.example/#reset="), "the token goes in the fragment, never to a server log"
    assert "30 minutos" in text

    token = link.split("#reset=", 1)[1]
    response = client.post("/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 200 and response.json()["user"]["email"] == "directora@banda.org"
    assert "scoremaster_session=" in response.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 200
    again = client.post("/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})
    assert again.status_code == 400 and "caducado" in again.json()["detail"]


@pytest.mark.real_auth
def test_the_configuration_says_whether_recovery_is_available(client):
    assert client.get("/auth/config").json()["password_reset_enabled"] is True
    app.dependency_overrides[get_mailer] = lambda: None
    assert client.get("/auth/config").json()["password_reset_enabled"] is False
    assert client.post("/auth/password/forgot", json={"email": "directora@banda.org"}).status_code == 404


def test_the_repository_keeps_only_the_last_link_of_each_account(postgres_engine):
    from datetime import datetime, timezone
    from uuid import uuid4

    from backend.application.accounts import PasswordReset, User
    accounts = PostgresAccountRepository(postgres_engine)
    user = User(uuid4(), "a@b.org", "A")
    accounts.add_user(user)
    expires = datetime(2026, 10, 29, 18, tzinfo=timezone.utc)
    accounts.add_password_reset(PasswordReset(user.id, "a" * 64, expires))
    accounts.add_password_reset(PasswordReset(user.id, "b" * 64, expires))
    assert accounts.password_reset_by_hash("a" * 64) is None
    assert accounts.password_reset_by_hash("b" * 64) == PasswordReset(user.id, "b" * 64, expires)
    accounts.delete_password_resets(user.id)
    assert accounts.password_reset_by_hash("b" * 64) is None


@pytest.mark.real_auth
def test_asked_for_in_english_the_answer_and_the_email_are_in_english(client):
    client.post("/auth/register", json={"email": "conductor@band.org", "password": PASSWORD})
    client.cookies.clear()
    response = client.post("/auth/password/forgot", json={"email": "conductor@band.org"}, headers={"Accept-Language": "en"})
    assert response.json()["detail"].startswith("If there is an account with that email")
    [(_, subject, text)] = client.outbox.messages
    assert subject == "ScoreMaster: choose a new password"
    assert "expires in 30 minutes" in text and "/#reset=" in text
