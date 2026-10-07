"""Works read once and kept across restarts (2026-10-07: on Render's free plan reading a band score with
music21 took about three minutes, for its audio and again for every rehearsal proposal, and the server
forgot it whenever it slept). Kind 'score' is the parsed musical model, 'playback' the sounding timeline.
Keyed by the content hash of the uploaded file: whoever sends that file may use it, so no owner is needed."""
from alembic import op
import sqlalchemy as sa

revision = '0008_prepared_works'
down_revision = '0007_ensembles'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prepared_works',
        sa.Column('source_sha256', sa.String(64), primary_key=True),
        sa.Column('kind', sa.String(20), primary_key=True),
        sa.Column('version', sa.String(40), nullable=False),
        sa.Column('data', sa.LargeBinary, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind in ('score', 'playback')", name='ck_prepared_works_kind'),
    )


def downgrade():
    op.drop_table('prepared_works')
