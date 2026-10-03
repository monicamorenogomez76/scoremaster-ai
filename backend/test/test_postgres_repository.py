from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.application.analysis_repository import AnalysisRecord
from backend.infrastructure.analysis_repository import PostgresAnalysisRepository
from backend.infrastructure.database import database_engine


def test_migrate_empty_database_and_repeat_upgrade(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config('alembic.ini')
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
        assert 'analyses' in inspect(connection).get_table_names()
        command.check(config)


def test_repository_roundtrip_versions_and_distinct_executions(postgres_engine):
    repo = PostgresAnalysisRepository(postgres_engine)
    record = AnalysisRecord('a' * 64, {'grade': 2}, {'minutes': 30}, {'tempo': 80})
    assert repo.save(record) == record.analysis_id
    loaded = repo.get(record.analysis_id)
    assert loaded.result == record.result
    assert loaded.configuration == record.configuration
    assert loaded.features == record.features
    assert loaded.algorithm_version == record.algorithm_version
    assert loaded.created_at.tzinfo is not None
    second = AnalysisRecord('a' * 64, {'grade': 3})
    repo.save(second)
    assert repo.get(record.analysis_id).result == {'grade': 2}
    assert repo.get(second.analysis_id).result == {'grade': 3}
    assert repo.get(uuid4()) is None


def test_duplicate_id_rolls_back_without_corrupting_original(postgres_engine):
    repo = PostgresAnalysisRepository(postgres_engine)
    record = AnalysisRecord('b' * 64, {'grade': 1})
    repo.save(record)
    with pytest.raises(IntegrityError):
        repo.save(AnalysisRecord('c' * 64, {'grade': 6}, analysis_id=record.analysis_id))
    assert repo.get(record.analysis_id).result == {'grade': 1}
    repo.save(AnalysisRecord('c' * 64, {'grade': 3}))


def test_storage_rejects_non_postgres_engine():
    with pytest.raises(ValueError, match='PostgreSQL'):
        database_engine('sqlite://')


def test_generate_next_migration_with_repository_template(tmp_path):
    directory = tmp_path / 'migrations'
    (directory / 'versions').mkdir(parents=True)
    (directory / 'script.py.mako').write_text(Path('migrations/script.py.mako').read_text())
    config = Config('alembic.ini')
    config.set_main_option('script_location', str(directory))
    revision = command.revision(config, message='synthetic schema change', rev_id='test_revision')
    generated = Path(revision.path).read_text()
    compile(generated, revision.path, 'exec')
    assert "revision = 'test_revision'" in generated
