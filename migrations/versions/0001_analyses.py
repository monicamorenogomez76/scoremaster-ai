"""Versioned structured analyses; raw files and audio are deliberately absent."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_analyses'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('result', postgresql.JSONB(), nullable=False),
        sa.Column('configuration', postgresql.JSONB(), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=False),
        sa.Column('algorithm_version', sa.String(100), nullable=False),
        sa.Column('features_version', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_analyses_source_sha256', 'analyses', ['source_sha256'])


def downgrade():
    op.drop_index('ix_analyses_source_sha256', table_name='analyses')
    op.drop_table('analyses')
