"""Email verification (2026-10-30). The administration (ADMIN_EMAILS) and the invitations to rate are decided by the
email of the account, and registration did not prove it: anyone could register the administration's email first. A new
account now gets a one-time link (24 hours) to confirm it; signing in with a verified Google email or using a password
recovery link confirm it too. In production, an unconfirmed email is neither administration nor invited. Accounts
created before are taken as confirmed."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import auth_routes
from backend.app.dependencies import get_account_repository, get_mailer, invitation_email, is_admin
from backend.app.main import app
from backend.application.accounts import User
from backend.application.auth import VERIFY_HOURS, AuthService, InvalidResetLink, LoginLimiter
from backend.infrastructure.account_repository import PostgresAccountRepository
from backend.test.account_fakes import InMemoryAccounts
from backend.test.test_auth_service import PASSWORD, Clock
from uuid import uuid4


@pytest.fixture
def service():
    clock = Clock()
    auth = AuthService(InMemoryAccounts(), clock=clock, limiter=LoginLimiter(clock=clock),
                       reset_limiter=LoginLimiter(3, clock=clock))
    auth.clock_handle = clock
    return auth


def test_a_new_account_confirms_its_email_with_a_one_time_link(service):
    user = service.register("directora@banda.org", PASSWORD, "Directora", ip="10.0.0.1").user
    assert user.email_verified is False
    token = service.request_email_verification(user, ip="10.0.0.1")
    assert token not in str(service.accounts.verifications), "only the SHA-256 is stored"
    assert service.verify_email(token, ip="10.0.0.1").email_verified is True
    assert service.accounts.user_by_email("directora@banda.org").email_verified is True
    with pytest.raises(InvalidResetLink):
        service.verify_email(token, ip="10.0.0.1")


def test_a_verification_link_expires(service):
    user = service.register("directora@banda.org", PASSWORD, "Directora", ip="10.0.0.1").user
    token = service.request_email_verification(user, ip="10.0.0.1")
    service.clock_handle.now += timedelta(hours=VERIFY_HOURS, minutes=1)
    with pytest.raises(InvalidResetLink):
        service.verify_email(token, ip="10.0.0.1")


def test_google_and_a_password_recovery_link_confirm_the_email(service):
    assert service.google("sub-1", "nueva@banda.org", True, "Nueva", ip="").user.email_verified is True
    service.register("musico@banda.org", PASSWORD, "Músico", ip="")
    _, token = service.request_password_reset("musico@banda.org", ip="")
    assert service.reset_password(token, "otra contraseña larga", ip="").user.email_verified is True


def test_in_production_an_unconfirmed_email_is_neither_administration_nor_invited(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@banda.org")
    unconfirmed = User(uuid4(), "admin@banda.org", "Admin")
    confirmed = User(uuid4(), "admin@banda.org", "Admin", email_verified=True)
    monkeypatch.setenv("APP_ENV", "development")
    assert is_admin(unconfirmed) and invitation_email(unconfirmed) == "admin@banda.org", "local work and CI are not stopped"
    monkeypatch.setenv("APP_ENV", "production")
    assert not is_admin(unconfirmed) and invitation_email(unconfirmed) is None
    assert is_admin(confirmed) and invitation_email(confirmed) == "admin@banda.org"


class Outbox:
    def __init__(self):
        self.messages = []

    def send(self, to, subject, text):
        self.messages.append((to, subject, text))


@pytest.fixture
def client(postgres_engine, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://scoremaster.example")
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


def _token(message):
    return next(word for word in message[2].split() if "#verify=" in word).split("#verify=", 1)[1]


@pytest.mark.real_auth
def test_over_http_registering_sends_the_link_and_opening_it_confirms(client):
    registered = client.post("/auth/register", json={"email": "directora@banda.org", "password": PASSWORD},
                             headers={"Accept-Language": "en"})
    assert registered.json()["user"]["email_verified"] is False
    [message] = client.outbox.messages
    assert message[0] == "directora@banda.org" and message[1] == "ScoreMaster: confirm your email"
    assert "https://scoremaster.example/#verify=" in message[2] and "24 hours" in message[2]
    confirmed = client.post("/auth/email/verify", json={"token": _token(message)})
    assert confirmed.status_code == 200 and confirmed.json() == {"email_verified": True}
    assert client.get("/auth/me").json()["user"]["email_verified"] is True
    assert client.post("/auth/email/verify", json={"token": _token(message)}).status_code == 400


@pytest.mark.real_auth
def test_another_link_can_be_asked_for_three_times_an_hour(client):
    csrf = client.post("/auth/register", json={"email": "directora@banda.org", "password": PASSWORD}).json()["csrf_token"]
    assert client.post("/auth/email/resend").status_code == 403, "it needs the CSRF token"
    answers = [client.post("/auth/email/resend", headers={"X-CSRF-Token": csrf}).status_code for _ in range(3)]
    assert answers == [202, 202, 202]
    assert len(client.outbox.messages) == 3, "the one of the registration and two more: three an hour"


@pytest.mark.real_auth
def test_the_app_is_told_whether_the_email_must_be_confirmed(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert client.get("/auth/config").json()["email_verification"] is False, "not asked locally nor in CI"
    monkeypatch.setenv("APP_ENV", "production")
    assert client.get("/auth/config").json()["email_verification"] is True
    app.dependency_overrides[get_mailer] = lambda: None
    assert client.get("/auth/config").json()["email_verification"] is False, "without mail it could never be confirmed"
