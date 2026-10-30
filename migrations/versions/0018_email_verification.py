"""Email verification (2026-10-30): when an account confirmed its email, and the one-time links that confirm it (kept
only as the SHA-256 of their token). The accounts created before are taken as confirmed: the administration keeps
its role after the deploy."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0018_email_verification'
down_revision = '0017_ai_usage'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET email_verified_at = created_at")
    op.create_table(
        'email_verifications',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_verifications_user_id', 'email_verifications', ['user_id'])


def downgrade():
    op.drop_index('ix_email_verifications_user_id', table_name='email_verifications')
    op.drop_table('email_verifications')
    op.drop_column('users', 'email_verified_at')
