"""Concerts with their programme and rehearsal pattern; rehearsals linked to a concert, fixed against
replanning, with a phase and the director's review."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006_concerts'
down_revision = '0005_rehearsals'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('concerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('scheduled_on', sa.Date(), nullable=False),
        sa.Column('starts_at', sa.String(5), nullable=True),
        sa.Column('place', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('work_ids', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('schedule', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_concerts_user_id', 'concerts', ['user_id', 'scheduled_on'])
    op.add_column('rehearsals', sa.Column('concert_id', postgresql.UUID(as_uuid=True),
                                          sa.ForeignKey('concerts.id', ondelete='SET NULL'), nullable=True))
    op.add_column('rehearsals', sa.Column('fixed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('rehearsals', sa.Column('phase', sa.String(20), nullable=True))
    op.add_column('rehearsals', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rehearsals', sa.Column('review_notes', sa.Text(), nullable=False, server_default=''))
    op.create_index('ix_rehearsals_concert_id', 'rehearsals', ['concert_id'])


def downgrade():
    op.drop_index('ix_rehearsals_concert_id', table_name='rehearsals')
    for column in ('review_notes', 'reviewed_at', 'phase', 'fixed', 'concert_id'):
        op.drop_column('rehearsals', column)
    op.drop_index('ix_concerts_user_id', table_name='concerts')
    op.drop_table('concerts')
