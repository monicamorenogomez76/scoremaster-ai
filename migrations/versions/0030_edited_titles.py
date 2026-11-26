"""The title and composer the director gives a work (2026-11-25): kept when its file is analysed again, whose MusicXML says
others («1812Overture_tousignant» is found by nobody)."""
from alembic import op
import sqlalchemy as sa

revision = '0030_edited_titles'
down_revision = '0029_old_band_names'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('works', sa.Column('title_edited', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('works', 'title_edited')
