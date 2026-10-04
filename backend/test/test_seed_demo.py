"""Demo user for the professor and the browser tests: created once, from environment variables."""
import pytest

from backend.app.seed_demo import seed_demo_user
from backend.application.auth import AuthService
from backend.infrastructure.account_repository import PostgresAccountRepository


def test_the_demo_user_is_created_once_and_can_sign_in(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)

    assert seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123") == "created"
    assert seed_demo_user(accounts, "demo@scoremaster.local", "demo-password-123") == "exists"
    assert AuthService(accounts).login("demo@scoremaster.local", "demo-password-123", ip="127.0.0.1").user.email == \
        "demo@scoremaster.local"


def test_without_credentials_nothing_is_created(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)
    assert seed_demo_user(accounts, "", "") == "skipped"
    with pytest.raises(ValueError):
        seed_demo_user(accounts, "demo@scoremaster.local", "corta")
