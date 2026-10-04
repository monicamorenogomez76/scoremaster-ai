"""Accounts, server-side sessions (token hashes only) and an audit trail of authentication events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002_users_sessions'
down_revision = '0001_analyses'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(254), nullable=False, unique=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('google_sub', sa.String(255), nullable=True, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_table('audit_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event', sa.String(50), nullable=False),
        sa.Column('ip', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table('audit_events')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_table('sessions')
    op.drop_table('users')
