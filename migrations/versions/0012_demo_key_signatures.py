"""The demo works saved before the key signatures were fixed (2026-10-14) get the regenerated file of
demo/. One KeySignature shared by every part had been transposed once per transposing instrument
(fifths 11-13) and the notation engine refused it. The notes are the same, so the analyses and the
prepared models follow the new hash instead of being read again with music21."""
import hashlib
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '0012_demo_key_signatures'
down_revision = '0011_ai_explanations'
branch_labels = None
depends_on = None

DEMO_DIR = Path(__file__).resolve().parents[2] / 'demo'
# sha256 of the files published in #93, by the name of their fixed version.
BROKEN = {
    'marcha-de-la-plaza.musicxml': 'f0e98abb551193ec6de9a365d7b0d48da1b49a9a72de88d24a1437c2384908f1',
    'andante-y-danza.musicxml': '5254375ebcefcc59e861bc33055202e423607f5474c92422575ca2268eb78c4c',
    'coral-para-principiantes.musicxml': 'b03866f277447ecf0cf4ce92e484ca5d0e3aff5c1bee0362569a157698d0d852',
}


def upgrade():
    connection = op.get_bind()
    for name, old in BROKEN.items():
        source = (DEMO_DIR / name).read_bytes()
        new = hashlib.sha256(source).hexdigest()
        connection.execute(sa.text('UPDATE works SET source = :source, source_sha256 = :new, size = :size, updated_at = now() '
                                   'WHERE source_sha256 = :old'), {'source': source, 'new': new, 'size': len(source), 'old': old})
        connection.execute(sa.text('UPDATE analyses SET source_sha256 = :new WHERE source_sha256 = :old'), {'new': new, 'old': old})
        # A model already prepared under the new hash wins; otherwise the old one is kept under it.
        connection.execute(sa.text('DELETE FROM prepared_works p WHERE p.source_sha256 = :old AND EXISTS '
                                   '(SELECT 1 FROM prepared_works n WHERE n.source_sha256 = :new AND n.kind = p.kind)'),
                           {'new': new, 'old': old})
        connection.execute(sa.text('UPDATE prepared_works SET source_sha256 = :new WHERE source_sha256 = :old'),
                           {'new': new, 'old': old})


def downgrade():
    """The broken files are not restored: the fixed ones have the same notes."""
