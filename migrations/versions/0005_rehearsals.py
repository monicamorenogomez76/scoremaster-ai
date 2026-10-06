"""Saved rehearsals: date, time, duration, place, objectives, works and an agenda of blocks."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005_rehearsals'
down_revision = '0004_work_preparation'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rehearsals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheduled_on', sa.Date(), nullable=False),
        sa.Column('starts_at', sa.String(5), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('place', sa.String(200), nullable=True),
        sa.Column('objectives', sa.Text(), nullable=False, server_default=''),
        sa.Column('work_ids', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('blocks', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('duration_minutes between 10 and 600', name='ck_rehearsals_duration'))
    op.create_index('ix_rehearsals_user_id', 'rehearsals', ['user_id', 'scheduled_on'])


def downgrade():
    op.drop_index('ix_rehearsals_user_id', table_name='rehearsals')
    op.drop_table('rehearsals')
