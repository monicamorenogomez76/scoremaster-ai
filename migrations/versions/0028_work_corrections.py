"""The notes the director corrected in a work (2026-11-22), in order: the work's file already has them, and each one is
kept to list it and to undo the last."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0028_work_corrections'
down_revision = '0027_reading_doubts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'work_corrections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('work_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('works.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('correction', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_work_corrections_work_id', 'work_corrections', ['work_id', 'created_at'])


def downgrade():
    op.drop_index('ix_work_corrections_work_id', table_name='work_corrections')
    op.drop_table('work_corrections')
