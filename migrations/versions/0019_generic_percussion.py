"""A generic percussion in the catalog (2026-11-02): «Percussion 1» of «Arabian Dances» plays marimba, low tom, finger
cymbals and suspended cymbal, and no instrument of the catalog named it. A database created from the seed after this
change already has it (0015 reads the seed); this one adds it where it is missing, with the names it is written with."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name, seed_instruments

revision = '0019_generic_percussion'
down_revision = '0018_email_verification'
branch_labels = None
depends_on = None

FIELDS = ('section', 'family', 'variant', 'transposition', 'label_es', 'label_en', 'sound', 'rehearsal_group')


def upgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM instruments WHERE id = 'percussion'")).first():
        return
    [item] = [entry for entry in seed_instruments() if entry['id'] == 'percussion']
    position = connection.execute(sa.text('SELECT COALESCE(MAX(position), -1) + 1 FROM instruments')).scalar()
    connection.execute(sa.text('INSERT INTO instruments (id, position, ' + ', '.join(FIELDS) + ') VALUES (:id, :position, '
                               + ', '.join(':' + field for field in FIELDS) + ')'),
                       {'id': 'percussion', 'position': position, **{field: item.get(field) for field in FIELDS}})
    for alias in item['aliases']:
        key = normalize_instrument_name(alias)
        connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                                   "SELECT 'percussion', CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) WHERE NOT EXISTS "
                                   "(SELECT 1 FROM instrument_names WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                           {'name': alias, 'key': key})


def downgrade():
    op.execute("DELETE FROM instruments WHERE id = 'percussion'")
