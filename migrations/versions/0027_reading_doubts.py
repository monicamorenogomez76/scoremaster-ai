"""The doubts of the PDF reader kept with each work (2026-11-22): the measures it took from a part because the score's
staff read otherwise, and the parts the director already reviewed. Null for a work never read from a PDF."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0027_reading_doubts'
down_revision = '0026_chimes_abbreviated'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('works', sa.Column('reading_doubts', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('works', 'reading_doubts')
