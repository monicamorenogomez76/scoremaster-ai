"""The instrument catalog in the database (2026-10-28): the instruments and every name they are written with, loaded
from the seed (backend/domain/instrument_catalog.json). Common rows have no owner; the owner column is for the names
and instruments an account adds. A name never names two instruments for the same account."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from backend.domain.instrument_catalog import normalize_instrument_name, seed_instruments

revision = '0015_instrument_catalog'
down_revision = '0014_pdf_imports'
branch_labels = None
depends_on = None

FIELDS = ('section', 'family', 'variant', 'transposition', 'label_es', 'label_en', 'sound', 'rehearsal_group')


def upgrade():
    instruments = op.create_table(
        'instruments',
        sa.Column('id', sa.String(80), primary_key=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(20), nullable=False),
        sa.Column('family', sa.String(40), nullable=False),
        sa.Column('variant', sa.String(40), nullable=True),
        sa.Column('transposition', sa.String(4), nullable=True),
        sa.Column('label_es', sa.String(80), nullable=False),
        sa.Column('label_en', sa.String(80), nullable=False),
        sa.Column('sound', sa.String(40), nullable=True),
        sa.Column('rehearsal_group', sa.String(20), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    names = op.create_table(
        'instrument_names',
        sa.Column('id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('instrument_id', sa.String(80), sa.ForeignKey('instruments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('name_key', sa.String(160), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_instrument_names_instrument_id', 'instrument_names', ['instrument_id'])
    op.create_index('uq_instrument_names_common', 'instrument_names', ['name_key'], unique=True,
                    postgresql_where=sa.text('owner_id IS NULL'))
    op.create_index('uq_instrument_names_owner', 'instrument_names', ['owner_id', 'name_key'], unique=True,
                    postgresql_where=sa.text('owner_id IS NOT NULL'))

    seed = seed_instruments()
    op.bulk_insert(instruments, [dict({'id': item['id'], 'position': position},
                                      **{field: item.get(field) for field in FIELDS})
                                 for position, item in enumerate(seed)])
    rows, seen = [], set()
    for item in seed:
        for alias in item['aliases']:
            key = normalize_instrument_name(alias)
            if key not in seen:
                seen.add(key)
                rows.append({'instrument_id': item['id'], 'name': alias, 'name_key': key})
    op.bulk_insert(names, rows)


def downgrade():
    op.drop_table('instrument_names')
    op.drop_table('instruments')
