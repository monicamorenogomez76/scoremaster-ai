"""Which repairs a work read from a PDF has been through (2026-11-06): each start downloaded every one to look at it, and Neon's
free plan transfers 5 GB a month. Works read before stay empty and are looked at once more."""
from alembic import op
import sqlalchemy as sa

revision = '0020_pdf_imports_repaired'
down_revision = '0019_generic_percussion'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pdf_imports', sa.Column('repaired_version', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('pdf_imports', 'repaired_version')
