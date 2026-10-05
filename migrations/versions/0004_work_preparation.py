"""Preparation status of each work (review, preparing, ready, archived), independent of its difficulty."""
from alembic import op
import sqlalchemy as sa

revision = '0004_work_preparation'
down_revision = '0003_works_bands'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('works', sa.Column('preparation_status', sa.String(20), nullable=False, server_default='review'))
    op.create_check_constraint('ck_works_preparation_status', 'works',
                               "preparation_status in ('review', 'preparing', 'ready', 'archived')")


def downgrade():
    op.drop_constraint('ck_works_preparation_status', 'works', type_='check')
    op.drop_column('works', 'preparation_status')
