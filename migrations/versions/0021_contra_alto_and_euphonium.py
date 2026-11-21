"""The contra-alto clarinet and more names of the euphonium (2026-11-20): «Arabian Dances» has an «E♭ Contra Alto Clarinet»,
a «Baritone T.C.» and a «Baritone/ Euphonium», and no instrument of the catalog named them, so they played as a piano. A
database created from the seed after this change already has them (0015 reads the seed); this one adds what is missing."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name, seed_instruments

revision = '0021_contra_alto_and_euphonium'
down_revision = '0020_pdf_imports_repaired'
branch_labels = None
depends_on = None

FIELDS = ('section', 'family', 'variant', 'transposition', 'label_es', 'label_en', 'sound', 'rehearsal_group')
NEW_INSTRUMENT = 'clarinet.contra_alto'
EUPHONIUM_NAMES = ('baritone/euphonium', 'baritone euphonium', 'euphonium/baritone', 'baritone t.c.', 'baritone b.c.',
                   'baritone tc', 'baritone bc', 'euphonium t.c.', 'euphonium b.c.')


def _add_name(connection, instrument_id: str, name: str) -> None:
    connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                               "SELECT CAST(:instrument AS VARCHAR), CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) "
                               "WHERE NOT EXISTS (SELECT 1 FROM instrument_names "
                               "WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                       {'instrument': instrument_id, 'name': name, 'key': normalize_instrument_name(name)})


def upgrade():
    connection = op.get_bind()
    [item] = [entry for entry in seed_instruments() if entry['id'] == NEW_INSTRUMENT]
    if not connection.execute(sa.text("SELECT 1 FROM instruments WHERE id = :id"), {'id': NEW_INSTRUMENT}).first():
        position = connection.execute(sa.text('SELECT COALESCE(MAX(position), -1) + 1 FROM instruments')).scalar()
        connection.execute(sa.text('INSERT INTO instruments (id, position, ' + ', '.join(FIELDS) + ') VALUES (:id, :position, '
                                   + ', '.join(':' + field for field in FIELDS) + ')'),
                           {'id': NEW_INSTRUMENT, 'position': position, **{field: item.get(field) for field in FIELDS}})
    for alias in item['aliases']:
        _add_name(connection, NEW_INSTRUMENT, alias)
    for alias in EUPHONIUM_NAMES:
        _add_name(connection, 'euphonium', alias)


def downgrade():
    op.execute("DELETE FROM instruments WHERE id = 'clarinet.contra_alto'")
    keys = ', '.join("'" + normalize_instrument_name(name) + "'" for name in EUPHONIUM_NAMES)
    op.execute(f"DELETE FROM instrument_names WHERE instrument_id = 'euphonium' AND owner_id IS NULL AND name_key IN ({keys})")
