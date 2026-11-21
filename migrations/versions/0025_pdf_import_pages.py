"""The pages read by the reader's helping machines, until the main one joins the work (2026-11-21, «1812»): they go
through ScoreMaster with the job's token, never through GitHub, whose artifacts and logs are public. They go with the
PDFs when the work arrives or the reading fails."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0025_pdf_import_pages'
down_revision = '0024_score_margin_names'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pdf_import_pages',
        sa.Column('import_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pdf_imports.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('file_number', sa.Integer(), primary_key=True),
        sa.Column('page_number', sa.Integer(), primary_key=True),
        sa.Column('musicxml', sa.LargeBinary(), nullable=False))


def downgrade() -> None:
    op.drop_table('pdf_import_pages')
