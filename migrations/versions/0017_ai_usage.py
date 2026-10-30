"""AI usage for the administration's panel (M5, 2026-10-30): every real call to the model, cache hit and discarded
answer, with its purpose, model, prompt version, outcome, latency and tokens. No text and no account."""
from alembic import op
import sqlalchemy as sa

revision = '0017_ai_usage'
down_revision = '0016_password_resets'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_usage',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('purpose', sa.String(30), nullable=False),
        sa.Column('model', sa.String(80), nullable=False),
        sa.Column('prompt_version', sa.String(80), nullable=False),
        sa.Column('event', sa.String(20), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
    )
    op.create_index('ix_ai_usage_created_at', 'ai_usage', ['created_at'])


def downgrade():
    op.drop_index('ix_ai_usage_created_at', table_name='ai_usage')
    op.drop_table('ai_usage')
