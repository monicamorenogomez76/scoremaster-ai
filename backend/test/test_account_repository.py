"""PostgreSQL account repository (plan phase 1)."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.application.accounts import DuplicateEmail, StoredSession, User
from backend.infrastructure.account_repository import PostgresAccountRepository


def test_users_sessions_and_events_round_trip(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)
    user = User(uuid4(), "a@b.org", "A", password_hash="$argon2id$hash")
    accounts.add_user(user)
    with pytest.raises(DuplicateEmail):
        accounts.add_user(User(uuid4(), "a@b.org", "Otra"))

    assert accounts.user_by_email("a@b.org") == user
    accounts.link_google(user.id, "google-1")
    assert accounts.user_by_google_sub("google-1").id == user.id

    expires = datetime(2026, 10, 11, tzinfo=timezone.utc)
    session = StoredSession(user.id, "h" * 64, "csrf", expires)
    accounts.add_session(session)
    assert accounts.session_by_token_hash("h" * 64) == session
    accounts.delete_session("h" * 64)
    assert accounts.session_by_token_hash("h" * 64) is None

    accounts.record_event(user.id, "login", "10.0.0.1")
    accounts.record_event(None, "login_failed", "10.0.0.2")
    with postgres_engine.connect() as connection:
        assert connection.execute(text("select count(*) from audit_events")).scalar() == 2


def test_deleting_a_user_deletes_their_sessions(postgres_engine):
    accounts = PostgresAccountRepository(postgres_engine)
    user = User(uuid4(), "a@b.org", "A")
    accounts.add_user(user)
    accounts.add_session(StoredSession(user.id, "h" * 64, "csrf", datetime.now(timezone.utc) + timedelta(days=1)))
    with postgres_engine.begin() as connection:
        connection.execute(text("delete from users"))
    assert accounts.session_by_token_hash("h" * 64) is None
