"""Publisher grades of a work, typed in by its owner with their source (
2026-10-14): the original label, its value on the 1-6 scale, the source, an optional link and the date
it was consulted. Deleted with the work or the account."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0013_work_external_grades'
down_revision = '0012_demo_key_signatures'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'work_external_grades',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('work_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('works.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scale', sa.String(20), nullable=False),
        sa.Column('label', sa.String(40), nullable=False),
        sa.Column('grade', sa.Float(), nullable=False),
        sa.Column('source', sa.String(200), nullable=False),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('consulted_on', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_work_external_grades_work_id', 'work_external_grades', ['work_id'])


def downgrade():
    op.drop_index('ix_work_external_grades_work_id', table_name='work_external_grades')
    op.drop_table('work_external_grades')
