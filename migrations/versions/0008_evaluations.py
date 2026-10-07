"""Evaluation campaigns: passages of the director's works with ScoreLint's hidden prediction,
invitations by email with the evaluator's profile, and their ratings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0008_evaluations'
down_revision = '0007_ensembles'
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table('evaluation_campaigns',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('owner_id', uuid, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(10), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('draft', 'open', 'closed')", name='ck_evaluation_campaigns_status'))
    op.create_index('ix_evaluation_campaigns_owner_id', 'evaluation_campaigns', ['owner_id'])
    op.create_table('evaluation_passages',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('campaign_id', uuid, sa.ForeignKey('evaluation_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('work_id', uuid, sa.ForeignKey('works.id', ondelete='CASCADE'), nullable=False),
        sa.Column('work_title', sa.String(300), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('parts', postgresql.JSONB(), nullable=False),
        sa.Column('measure_range', sa.String(20), nullable=False),
        sa.Column('label', sa.String(300), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(), nullable=False))
    op.create_index('ix_evaluation_passages_campaign_id', 'evaluation_passages', ['campaign_id'])
    op.create_table('evaluation_invitations',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('campaign_id', uuid, sa.ForeignKey('evaluation_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('experience_level', sa.String(20), nullable=True),
        sa.Column('main_instrument', sa.String(100), nullable=True),
        sa.UniqueConstraint('campaign_id', 'email', name='uq_evaluation_invitations_email'))
    op.create_index('ix_evaluation_invitations_email', 'evaluation_invitations', ['email'])
    op.create_table('evaluation_ratings',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('passage_id', uuid, sa.ForeignKey('evaluation_passages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invitation_id', uuid, sa.ForeignKey('evaluation_invitations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('difficulty', sa.Integer(), nullable=False),
        sa.Column('critical', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('passage_id', 'invitation_id', name='uq_evaluation_ratings_once'),
        sa.CheckConstraint('difficulty between 1 and 6', name='ck_evaluation_ratings_difficulty'),
        sa.CheckConstraint('priority between 1 and 5', name='ck_evaluation_ratings_priority'))


def downgrade():
    op.drop_table('evaluation_ratings')
    op.drop_index('ix_evaluation_invitations_email', table_name='evaluation_invitations')
    op.drop_table('evaluation_invitations')
    op.drop_index('ix_evaluation_passages_campaign_id', table_name='evaluation_passages')
    op.drop_table('evaluation_passages')
    op.drop_index('ix_evaluation_campaigns_owner_id', table_name='evaluation_campaigns')
    op.drop_table('evaluation_campaigns')
