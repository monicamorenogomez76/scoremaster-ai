from alembic import context

from backend.infrastructure.analysis_repository import Base
import backend.infrastructure.account_repository  # noqa: F401  (registers the account tables)
import backend.infrastructure.library_repository  # noqa: F401  (registers works and bands)
from backend.infrastructure.database import database_engine

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError('Run migrations against a PostgreSQL connection.')
connection = config.attributes.get('connection')
if connection is not None:
    run(connection)
else:
    engine = database_engine()
    try:
        with engine.connect() as connection:
            run(connection)
    finally:
        engine.dispose()
