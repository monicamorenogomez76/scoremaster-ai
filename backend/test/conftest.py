import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from backend.infrastructure.database import database_engine

# Tests that need the background audio preparation turn it on themselves.
os.environ.setdefault('PLAYBACK_WARMUP', '0')


@pytest.fixture
def postgres_engine():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run real PostgreSQL integration tests.')
    admin = database_engine(url)
    schema = 'test_scoremaster_' + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(admin.url, connect_args={'options': f'-csearch_path={schema}', 'connect_timeout': 5})
    try:
        with engine.begin() as connection:
            config = Config('alembic.ini')
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()



def pytest_configure(config):
    config.addinivalue_line('markers', 'real_auth: use the real session and CSRF checks instead of the test user')


TEST_USER_EMAIL = 'test@scoremaster.local'


@pytest.fixture(autouse=True)
def signed_in_test_user(request):
    """Endpoints that need a session see a fixed test user, unless the test checks real authentication."""
    if request.node.get_closest_marker('real_auth'):
        yield
        return
    from backend.app.dependencies import authenticated_user, get_library_repository
    from backend.app.main import app
    from backend.application.accounts import User
    from backend.test.library_fakes import InMemoryLibrary
    user, library = User(uuid4(), TEST_USER_EMAIL, 'Test'), InMemoryLibrary()
    app.dependency_overrides[authenticated_user] = lambda: user
    app.dependency_overrides[get_library_repository] = lambda: library
    try:
        yield user
    finally:
        app.dependency_overrides.pop(authenticated_user, None)
        app.dependency_overrides.pop(get_library_repository, None)


@pytest.fixture(autouse=True)
def no_prepared_store():
    """Prepared works stay in memory, never in the database of DATABASE_URL, unless a test gives a store."""
    from backend.app.dependencies import get_playback_store, get_score_store
    from backend.app.main import app
    app.dependency_overrides[get_playback_store] = lambda: None
    app.dependency_overrides[get_score_store] = lambda: None
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_playback_store, None)
        app.dependency_overrides.pop(get_score_store, None)
