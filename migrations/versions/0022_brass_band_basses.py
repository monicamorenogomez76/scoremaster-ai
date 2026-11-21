"""The basses of brass bands are tubas (2026-11-21): «Eb Bass», «Bb Bass», «BBb Bass» and the German «Es-Bass» and
«B-Bass». A database created from the seed after this change already has them (0015 reads the seed); this one adds the
names that are missing."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name

revision = '0022_brass_band_basses'
down_revision = '0021_contra_alto_and_euphonium'
branch_labels = None
depends_on = None

NAMES = ('eb bass', 'bb bass', 'bbb bass', 'e flat bass', 'b flat bass', 'es bass', 'b bass')


def upgrade():
    connection = op.get_bind()
    for name in NAMES:
        connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                                   "SELECT 'tuba', CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) WHERE NOT EXISTS "
                                   "(SELECT 1 FROM instrument_names WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                           {'name': name, 'key': normalize_instrument_name(name)})


def downgrade():
    keys = ', '.join("'" + normalize_instrument_name(name) + "'" for name in NAMES)
    op.execute(f"DELETE FROM instrument_names WHERE instrument_id = 'tuba' AND owner_id IS NULL AND name_key IN ({keys})")
