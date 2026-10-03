import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url


def database_engine(url: str = '') -> Engine:
    url = url or os.environ.get('DATABASE_URL', '')
    if not url:
        raise ValueError('DATABASE_URL is required for persistent storage.')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql':
        raise ValueError('Persistent storage requires PostgreSQL.')
    if parsed.drivername in ('postgres', 'postgresql'):
        parsed = parsed.set(drivername='postgresql+psycopg')
    return create_engine(parsed, pool_pre_ping=True, connect_args={'connect_timeout': 5})
