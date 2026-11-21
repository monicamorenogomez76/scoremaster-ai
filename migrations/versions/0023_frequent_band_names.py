"""The frequent band instruments and names the catalog did not know (2026-11-21, review of band instrumentation): horn in
E♭, the E♭ tenor horn, the E♭ soprano cornet, the bass saxophone, crotales, celesta and the usual percussion of a band,
and the names and abbreviations the instruments of the catalog are printed with. A database created from the seed after
this change already has them (0015 reads the seed); this one adds what is missing, never twice."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name, seed_instruments

revision = '0023_frequent_band_names'
down_revision = '0022_brass_band_basses'
branch_labels = None
depends_on = None

FIELDS = ('section', 'family', 'variant', 'transposition', 'label_es', 'label_en', 'sound', 'rehearsal_group')
NEW = ('horn.eb', 'alto_horn', 'cornet.eb', 'saxophone.bass', 'crotales', 'celesta', 'wood_block', 'temple_blocks',
       'tam_tam', 'toms', 'tenor_drum', 'hi_hat', 'finger_cymbals', 'castanets', 'claves', 'maracas', 'guiro', 'cowbell',
       'cabasa', 'shaker', 'bongos', 'congas', 'vibraslap', 'whistle', 'sleigh_bells', 'wind_chimes', 'whip', 'ratchet')
WITH_NEW_NAMES = ('cornet.bb', 'clarinet.contrabass', 'clarinet.eb', 'glockenspiel', 'xylophone', 'marimba', 'timpani',
                  'snare_drum', 'bass_drum', 'suspended_cymbal', 'crash_cymbals', 'triangle', 'harp', 'double_bass',
                  'electric_bass', 'percussion')


def upgrade():
    connection = op.get_bind()
    seed = {item['id']: item for item in seed_instruments()}
    for instrument_id in NEW:
        if connection.execute(sa.text("SELECT 1 FROM instruments WHERE id = :id"), {'id': instrument_id}).first():
            continue
        position = connection.execute(sa.text('SELECT COALESCE(MAX(position), -1) + 1 FROM instruments')).scalar()
        connection.execute(sa.text('INSERT INTO instruments (id, position, ' + ', '.join(FIELDS) + ') VALUES (:id, :position, '
                                   + ', '.join(':' + field for field in FIELDS) + ')'),
                           {'id': instrument_id, 'position': position, **{field: seed[instrument_id].get(field) for field in FIELDS}})
    for instrument_id in NEW + WITH_NEW_NAMES:
        for alias in seed[instrument_id]['aliases']:
            connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                                       "SELECT CAST(:instrument AS VARCHAR), CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) "
                                       "WHERE NOT EXISTS (SELECT 1 FROM instrument_names "
                                       "WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                               {'instrument': instrument_id, 'name': alias, 'key': normalize_instrument_name(alias)})


def downgrade():
    op.execute("DELETE FROM instruments WHERE id IN (" + ", ".join("'" + item + "'" for item in NEW) + ")")
