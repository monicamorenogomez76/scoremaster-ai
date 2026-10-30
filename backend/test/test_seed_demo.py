"""Demo user for the professor and the browser tests: created once, from environment variables."""
import pytest

from backend.app.seed_demo import seed_demo_user
from backend.application.auth import AuthService
from backend.infrastructure.account_repository import PostgresAccountRepository


def test_the_demo_user_is_created_once_and_can_sign_in(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)

    assert seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123") == "created"
    assert seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123") == "exists"
    assert accounts.user_by_email("demo@scoremaster.local").email_verified, "no mailbox: taken as confirmed"
    assert AuthService(accounts).login("demo@scoremaster.local", "demo-password-123", ip="127.0.0.1").user.email == \
        "demo@scoremaster.local"


def test_without_credentials_nothing_is_created(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)
    assert seed_demo_user(accounts, "", "") == "skipped"
    with pytest.raises(ValueError):
        seed_demo_user(accounts, "demo@scoremaster.local", "corta")


def test_the_demo_password_follows_the_variable_and_old_sessions_are_closed(postgres_engine):
    """2026-10-14, Render: the demo account had been created with an earlier password, and changing
    DEMO_USER_PASSWORD did nothing. On every start the account's password now follows the variable."""
    from backend.application.auth import InvalidCredentials
    accounts = PostgresAccountRepository(postgres_engine)
    seed_demo_user(accounts, "demo@scoremaster.local", "contraseña-antigua")
    old_session = AuthService(accounts).login("demo@scoremaster.local", "contraseña-antigua", ip="127.0.0.1")

    assert seed_demo_user(accounts, "demo@scoremaster.local", "contraseña-nueva-del-tribunal") == "updated"

    assert AuthService(accounts).login("demo@scoremaster.local", "contraseña-nueva-del-tribunal", ip="127.0.0.1")
    with pytest.raises(InvalidCredentials):
        AuthService(accounts).login("demo@scoremaster.local", "contraseña-antigua", ip="127.0.0.2")
    assert AuthService(accounts).current(old_session.token) is None, "sessions opened with the old password end"


def test_the_same_password_changes_nothing(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)
    seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123")
    session = AuthService(accounts).login("demo@scoremaster.local", "demo-password-123", ip="127.0.0.1")
    assert seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123") == "exists"
    assert AuthService(accounts).current(session.token) is not None
