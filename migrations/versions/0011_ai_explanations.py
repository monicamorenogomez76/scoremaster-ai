"""Valid AI explanations kept for reuse (step 23, 2026-10-13: the free quota of gemini-3.8-flash is 20
requests a day). Keyed by the hash of the exact evidence, provider, model and prompt version; errors,
fallbacks and the demo are never kept."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0011_ai_explanations'
down_revision = '0010_llm_reviews'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_explanations',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('answer', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('ai_explanations')
