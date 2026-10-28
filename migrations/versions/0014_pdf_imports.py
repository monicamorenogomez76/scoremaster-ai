"""PDF scores (decided 2026-10-27): a work says whether it was read from a PDF, and each import keeps its
PDFs until the reader in GitHub Actions sends the work back. The import's one-time token is kept only as its sha256;
the PDFs are deleted when the result arrives. Deleted with the account."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0014_pdf_imports'
down_revision = '0013_work_external_grades'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('works', sa.Column('source_format', sa.String(10), nullable=False, server_default='musicxml'))
    op.create_table(
        'pdf_imports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='queued'),
        sa.Column('token_sha256', sa.String(64), nullable=True),
        sa.Column('pages_done', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pages_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.String(300), nullable=True),
        sa.Column('musicxml', sa.LargeBinary(), nullable=True),
        sa.Column('band_profile', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('total_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('work_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('works.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_pdf_imports_user_id', 'pdf_imports', ['user_id'])
    op.create_table(
        'pdf_import_files',
        sa.Column('import_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pdf_imports.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('position', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
    )


def downgrade():
    op.drop_table('pdf_import_files')
    op.drop_index('ix_pdf_imports_user_id', table_name='pdf_imports')
    op.drop_table('pdf_imports')
    op.drop_column('works', 'source_format')
