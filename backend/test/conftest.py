import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from backend.infrastructure.database import database_engine


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

