"""Works with their original MusicXML (private to their owner), analyses linked to owner and work,
and the band template of each user."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_works_bands'
down_revision = '0002_users_sessions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('works',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('composer', sa.String(300), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('source', sa.LargeBinary(), nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'source_sha256', name='uq_works_user_source'))
    op.create_index('ix_works_user_id', 'works', ['user_id'])
    op.add_column('analyses', sa.Column('user_id', postgresql.UUID(as_uuid=True),
                                        sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('analyses', sa.Column('work_id', postgresql.UUID(as_uuid=True),
                                        sa.ForeignKey('works.id', ondelete='CASCADE'), nullable=True))
    op.create_index('ix_analyses_user_id', 'analyses', ['user_id'])
    op.create_index('ix_analyses_work_id', 'analyses', ['work_id'])
    op.create_table('bands',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('profile', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('section_levels', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table('bands')
    op.drop_index('ix_analyses_work_id', table_name='analyses')
    op.drop_index('ix_analyses_user_id', table_name='analyses')
    op.drop_column('analyses', 'work_id')
    op.drop_column('analyses', 'user_id')
    op.drop_index('ix_works_user_id', table_name='works')
    op.drop_table('works')
