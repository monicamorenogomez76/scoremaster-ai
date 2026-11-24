"""The names of an American band edition of a century ago (2026-11-23, «The Ride of the Valkyries», arr. Laurendeau):
the D♭ piccolo, after the piccolo, and «Solo B♭ Clarinet», «Cornets», «Altos» (E♭ alto horns), «Tenors» (B♭ tenor
horns), «Basses» and «Timpany». A database created from the seed after this change already has them (0015 reads the
seed); this one adds them when they are missing, never twice."""
from alembic import op
import sqlalchemy as sa

from backend.domain.instrument_catalog import normalize_instrument_name

revision = '0029_old_band_names'
down_revision = '0028_work_corrections'
branch_labels = None
depends_on = None

PICCOLO_DB = {'id': 'piccolo.db', 'section': 'woodwinds', 'family': 'flute', 'variant': 'db_piccolo', 'transposition': 'Db',
              'label_es': 'Flautín en Re bemol', 'label_en': 'D♭ Piccolo', 'sound': 'piccolo', 'rehearsal_group': 'flutes'}
NAMES = {
    'piccolo.db': ('db piccolo', 'piccolo in db', 'd flat piccolo', 'des piccolo', 'flautin en reb', 'flautin en re bemol'),
    'clarinet.bb': ('solo clarinet', 'solo bb clarinet'),
    'cornet.bb': ('cornets', 'bb cornets'),
    'alto_horn': ('altos', 'alto horns', 'eb altos'),
    'baritone_horn': ('tenors', 'bb tenors'),
    'tuba': ('basses', 'bb basses', 'eb basses'),
    'timpani': ('timpany',),
}


def upgrade():
    connection = op.get_bind()
    exists = connection.execute(sa.text("SELECT 1 FROM instruments WHERE id = 'piccolo.db'")).first()
    piccolo = connection.execute(sa.text("SELECT position FROM instruments WHERE id = 'piccolo' AND owner_id IS NULL")).first()
    if not exists and piccolo is not None:
        connection.execute(sa.text("UPDATE instruments SET position = position + 1 WHERE position > :at"), {'at': piccolo.position})
        connection.execute(sa.text("INSERT INTO instruments (id, position, section, family, variant, transposition, label_es, "
                                   "label_en, sound, rehearsal_group) VALUES (:id, :position, :section, :family, :variant, "
                                   ":transposition, :label_es, :label_en, :sound, :rehearsal_group)"),
                           {**PICCOLO_DB, 'position': piccolo.position + 1})
    for instrument_id, names in NAMES.items():
        if not connection.execute(sa.text("SELECT 1 FROM instruments WHERE id = :id"), {'id': instrument_id}).first():
            continue
        for name in names:
            connection.execute(sa.text("INSERT INTO instrument_names (instrument_id, name, name_key) "
                                       "SELECT CAST(:instrument AS VARCHAR), CAST(:name AS VARCHAR), CAST(:key AS VARCHAR) "
                                       "WHERE NOT EXISTS (SELECT 1 FROM instrument_names "
                                       "WHERE name_key = CAST(:key AS VARCHAR) AND owner_id IS NULL)"),
                               {'instrument': instrument_id, 'name': name, 'key': normalize_instrument_name(name)})


def downgrade():
    for instrument_id, names in NAMES.items():
        if instrument_id == 'piccolo.db':
            continue
        keys = ', '.join("'" + normalize_instrument_name(name) + "'" for name in names)
        op.execute(f"DELETE FROM instrument_names WHERE instrument_id = '{instrument_id}' AND owner_id IS NULL "
                   f"AND name_key IN ({keys})")
    connection = op.get_bind()
    piccolo = connection.execute(sa.text("SELECT position FROM instruments WHERE id = 'piccolo.db'")).first()
    if piccolo is not None:
        op.execute("DELETE FROM instruments WHERE id = 'piccolo.db'")
        connection.execute(sa.text("UPDATE instruments SET position = position - 1 WHERE position > :at"), {'at': piccolo.position})
