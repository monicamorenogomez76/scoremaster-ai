"""«Chim.» for the chimes (2026-11-21, «1812»): the last staff of its score, the only name beside its staves the catalog
did not know. A database created from the seed after this change already has it (0015 reads the seed); this one adds
it when it is missing, never twice."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name

revision = '0026_chimes_abbreviated'
down_revision = '0025_pdf_import_pages'
branch_labels = None
depends_on = None

NAMES = {'chimes': ('chim',)}


def upgrade():
    connection = op.get_bind()
    for instrument_id, names in NAMES.items():
        for name in names:
            connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                                       "SELECT CAST(:instrument AS VARCHAR), CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) "
                                       "WHERE NOT EXISTS (SELECT 1 FROM instrument_names "
                                       "WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                               {'instrument': instrument_id, 'name': name, 'key': normalize_instrument_name(name)})


def downgrade():
    for instrument_id, names in NAMES.items():
        keys = ', '.join("'" + normalize_instrument_name(name) + "'" for name in names)
        op.execute(f"DELETE FROM instrument_names WHERE instrument_id = '{instrument_id}' AND owner_id IS NULL "
                   f"AND name_key IN ({keys})")
