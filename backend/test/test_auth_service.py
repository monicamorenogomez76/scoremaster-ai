"""Accounts and sessions (plan phase 1): email/password with Argon2, opaque server-side sessions."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.application.auth import (
    AuthService, InvalidCredentials, InvalidRegistration, LoginLimiter, TooManyAttempts, token_hash,
)
from backend.test.account_fakes import InMemoryAccounts

PASSWORD = "correct horse battery"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


@pytest.fixture
def service():
    clock = Clock()
    accounts = InMemoryAccounts()
    auth = AuthService(accounts, clock=clock, limiter=LoginLimiter(clock=clock))
    auth.clock_handle, auth.accounts = clock, accounts
    return auth


def test_registration_stores_an_argon2_hash_never_the_password(service):
    signed_in = service.register("Directora@Banda.org ", PASSWORD, "Directora", ip="10.0.0.1")

    user = service.accounts.user_by_email("directora@banda.org")
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert signed_in.user.email == "directora@banda.org"
    assert ("registered" in [event for _, event, _ in service.accounts.events])


@pytest.mark.parametrize("email, password", [("no-es-un-email", PASSWORD), ("a@b.org", "corta"), ("a@b.org", "x" * 300)])
def test_invalid_registrations_are_rejected(service, email, password):
    with pytest.raises(InvalidRegistration):
        service.register(email, password, "Nombre", ip="10.0.0.1")


def test_an_email_can_only_register_once(service):
    service.register("a@b.org", PASSWORD, "A", ip="10.0.0.1")
    with pytest.raises(InvalidRegistration):
        service.register("A@B.org", PASSWORD, "Otra", ip="10.0.0.1")


def test_login_opens_an_opaque_session_stored_only_as_a_hash(service):
    service.register("a@b.org", PASSWORD, "A", ip="10.0.0.1")
    signed_in = service.login("a@b.org", PASSWORD, ip="10.0.0.1")

    assert len(signed_in.token) >= 40 and signed_in.csrf_token
    assert signed_in.token not in service.accounts.sessions
    assert token_hash(signed_in.token) in service.accounts.sessions
    user, session = service.current(signed_in.token)
    assert user.email == "a@b.org" and session.csrf_token == signed_in.csrf_token


def test_unknown_email_and_wrong_password_fail_the_same_way(service):
    service.register("a@b.org", PASSWORD, "A", ip="10.0.0.1")
    with pytest.raises(InvalidCredentials) as unknown:
        service.login("nadie@b.org", PASSWORD, ip="10.0.0.1")
    with pytest.raises(InvalidCredentials) as wrong:
        service.login("a@b.org", "otra contraseña", ip="10.0.0.1")
    assert str(unknown.value) == str(wrong.value)
    assert [event for _, event, _ in service.accounts.events].count("login_failed") == 2


def test_repeated_failures_are_throttled_per_email_and_address(service):
    service.register("a@b.org", PASSWORD, "A", ip="10.0.0.1")
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            service.login("a@b.org", "mala contraseña", ip="10.0.0.1")
    with pytest.raises(TooManyAttempts):
        service.login("a@b.org", PASSWORD, ip="10.0.0.1")
    assert service.login("a@b.org", PASSWORD, ip="10.0.0.2").user.email == "a@b.org"

    service.clock_handle.now += timedelta(minutes=16)
    assert service.login("a@b.org", PASSWORD, ip="10.0.0.1").user.email == "a@b.org"


def test_sessions_expire_and_logout_closes_them(service):
    signed_in = service.register("a@b.org", PASSWORD, "A", ip="10.0.0.1")
    other = service.login("a@b.org", PASSWORD, ip="10.0.0.1")

    service.logout(signed_in.token)
    assert service.current(signed_in.token) is None
    assert service.current(other.token) is not None

    service.clock_handle.now += timedelta(days=8)
    assert service.current(other.token) is None
    assert service.current("token-inventado") is None


def test_a_google_account_is_created_once_and_linked_by_verified_email(service):
    first = service.google("google-sub-1", "Nueva@Banda.org", True, "Nueva", ip="10.0.0.1")
    again = service.google("google-sub-1", "nueva@banda.org", True, "Nueva", ip="10.0.0.1")
    assert first.user.id == again.user.id and first.user.password_hash is None

    service.register("clave@banda.org", PASSWORD, "Clave", ip="10.0.0.1")
    linked = service.google("google-sub-2", "clave@banda.org", True, "Clave", ip="10.0.0.1")
    assert linked.user.email == "clave@banda.org" and linked.user.google_sub == "google-sub-2"


def test_an_unverified_google_email_is_never_linked_to_an_existing_account(service):
    service.register("clave@banda.org", PASSWORD, "Clave", ip="10.0.0.1")
    with pytest.raises(InvalidCredentials):
        service.google("google-sub-3", "clave@banda.org", False, "Intruso", ip="10.0.0.1")
