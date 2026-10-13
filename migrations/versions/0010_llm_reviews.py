"""Independent reviews of evaluation passages by an LLM (step 22, method B). One per passage and
provider, model, prompt and features version: rerunning with the same versions never asks again,
and every review keeps what it was asked (features) for traceability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0010_llm_reviews'
down_revision = '0009_evaluations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'evaluation_llm_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('passage_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_passages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('model', sa.String(80), nullable=False),
        sa.Column('prompt_version', sa.String(60), nullable=False),
        sa.Column('features_version', sa.String(60), nullable=False),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('critical', sa.Boolean(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('main_factors', postgresql.JSONB(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('passage_id', 'provider', 'model', 'prompt_version', 'features_version',
                            name='uq_evaluation_llm_reviews_version'),
        sa.CheckConstraint('grade between 1 and 6', name='ck_evaluation_llm_reviews_grade'),
        sa.CheckConstraint('confidence between 0 and 1', name='ck_evaluation_llm_reviews_confidence'),
    )
    op.create_index('ix_evaluation_llm_reviews_passage_id', 'evaluation_llm_reviews', ['passage_id'])


def downgrade():
    op.drop_index('ix_evaluation_llm_reviews_passage_id', 'evaluation_llm_reviews')
    op.drop_table('evaluation_llm_reviews')
