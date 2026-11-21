"""The names beside the staves of a score (2026-11-21, «Arabian Dances»): abbreviations and plurals under a brace
(«Fls.», «Cls.», «Tpts.», «Hns.», «Bar./Euph.», «Shkr.»; «Flutes», «Trumpets», «F Horns»). A database created from the
seed after this change already has them (0015 reads the seed); this one adds the names that are missing, never twice."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name

revision = '0024_score_margin_names'
down_revision = '0023_frequent_band_names'
branch_labels = None
depends_on = None

NAMES = {
    'flute': ('fls', 'flutes', 'flts'), 'oboe': ('obs', 'oboes'), 'bassoon': ('bsns', 'bassoons', 'bsn'),
    'clarinet.bb': ('cls', 'clarinets', 'bb clarinets', 'clars'),
    'saxophone.alto': ('a saxes', 'alto saxophones', 'eb alto saxophones', 'alto saxes', 'a saxs'),
    'trumpet.bb': ('tpts', 'trumpets', 'bb trumpets'), 'horn.f': ('hns', 'horns', 'f horns', 'hrns'),
    'trombone.tenor': ('tbns', 'trbs'), 'euphonium': ('bar euph', 'bar euphonium', 'baritone euph'), 'shaker': ('shkr',),
}


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
