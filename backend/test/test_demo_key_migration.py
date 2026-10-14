"""Migration 0012 (2026-10-14): the demo works saved before the key signatures were fixed get the
regenerated file. The notes are the same, so their analyses and prepared models follow the new hash
instead of being read again with music21 on Render's free plan."""
import hashlib
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from backend.app.demo_content import DEMO_DIR
from backend.infrastructure.database import database_engine

OLD_MARCH = "f0e98abb551193ec6de9a365d7b0d48da1b49a9a72de88d24a1437c2384908f1"


def _upgrade(engine, revision):
    with engine.begin() as connection:
        config = Config('alembic.ini')
        config.attributes['connection'] = connection
        command.upgrade(config, revision)


@pytest.fixture
def engine_at_0011():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run real PostgreSQL integration tests.')
    admin = database_engine(url)
    schema = 'test_scoremaster_' + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(admin.url, connect_args={'options': f'-csearch_path={schema}', 'connect_timeout': 5})
    try:
        _upgrade(engine, '0011_ai_explanations')
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_the_saved_demo_works_get_the_fixed_file_and_keep_their_analysis(engine_at_0011):
    user, march, other = uuid4(), uuid4(), uuid4()
    with engine_at_0011.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, display_name) VALUES (:id, 'demo@banda.org', 'Demo')"), {"id": user})
        work = ("INSERT INTO works (id, user_id, title, file_name, source, source_sha256, size) "
                "VALUES (:id, :user, :title, :name, :source, :sha, 3)")
        connection.execute(text(work), {"id": march, "user": user, "title": "Marcha de la plaza",
                                        "name": "marcha-de-la-plaza.musicxml", "source": b"old", "sha": OLD_MARCH})
        connection.execute(text(work), {"id": other, "user": user, "title": "Persis", "name": "persis.musicxml",
                                        "source": b"own", "sha": "a" * 64})
        connection.execute(text("INSERT INTO analyses (id, source_sha256, result, configuration, features, algorithm_version, "
                                "features_version) VALUES (:id, :sha, '{}', '{}', '{}', 'v', 'v')"), {"id": uuid4(), "sha": OLD_MARCH})
        connection.execute(text("INSERT INTO prepared_works (source_sha256, kind, version, data) VALUES (:sha, 'score', 'v', 'x')"),
                           {"sha": OLD_MARCH})

    _upgrade(engine_at_0011, 'head')

    fixed = (DEMO_DIR / "marcha-de-la-plaza.musicxml").read_bytes()
    new = hashlib.sha256(fixed).hexdigest()
    with engine_at_0011.connect() as connection:
        rows = dict(connection.execute(text("SELECT title, source_sha256 FROM works")).all())
        source, size = connection.execute(text("SELECT source, size FROM works WHERE id = :id"), {"id": march}).one()
        assert (bytes(source), size, rows["Marcha de la plaza"]) == (fixed, len(fixed), new)
        assert rows["Persis"] == "a" * 64, "the director's own works are untouched"
        assert connection.execute(text("SELECT source_sha256 FROM analyses")).scalar_one() == new
        assert connection.execute(text("SELECT source_sha256 FROM prepared_works")).scalar_one() == new
