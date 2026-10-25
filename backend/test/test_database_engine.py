"""The database moves to Neon (2026-10-25): Render's free PostgreSQL expires after 30 days. The engine keeps the
TLS options of Neon's connection string and waits long enough for a suspended Neon compute to wake up."""
import pytest
from sqlalchemy import event

from backend.infrastructure.database import CONNECT_TIMEOUT_SECONDS, database_engine

NEON = "postgresql://owner:secret@ep-example-123456.eu-central-1.aws.neon.tech/scoremaster?sslmode=require&channel_binding=require"


def test_a_neon_url_keeps_its_tls_options_and_uses_psycopg():
    engine = database_engine(NEON)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.query == {"sslmode": "require", "channel_binding": "require"}
    finally:
        engine.dispose()


def test_the_connection_waits_for_a_suspended_compute():
    """Neon suspends its free compute after 5 minutes without use and takes a moment to wake up."""
    assert CONNECT_TIMEOUT_SECONDS >= 10
    engine = database_engine(NEON)
    seen = {}

    class Stop(Exception):
        pass

    @event.listens_for(engine, "do_connect")
    def capture(dialect, record, cargs, cparams):   # the parameters psycopg would receive, without connecting
        seen.update(cparams)
        raise Stop

    try:
        with pytest.raises(Stop):
            engine.connect()
        assert seen["connect_timeout"] == CONNECT_TIMEOUT_SECONDS and seen["sslmode"] == "require"
    finally:
        engine.dispose()


def test_a_local_url_is_not_forced_to_use_tls():
    """Compose's PostgreSQL has no TLS: nothing is added that the URL does not ask for."""
    engine = database_engine("postgresql+psycopg://scoremaster:x@127.0.0.1:5433/scoremaster")
    try:
        assert "sslmode" not in engine.url.query
    finally:
        engine.dispose()


@pytest.mark.parametrize("url", ["", "sqlite:///x.db"])
def test_only_postgresql_is_accepted(url, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError):
        database_engine(url)
