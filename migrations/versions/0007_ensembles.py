"""Several bands per director, one of them active: name, locality, rehearsal days, full template and
levels per section. The previous single template becomes the active band «Mi banda»; concerts are
played by one band."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0007_ensembles'
down_revision = '0006_concerts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ensembles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('locality', sa.String(200), nullable=True),
        sa.Column('place', sa.String(200), nullable=True),
        sa.Column('rehearsal_weekdays', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('rehearsal_time', sa.String(5), nullable=True),
        sa.Column('rehearsal_minutes', sa.Integer(), nullable=True),
        sa.Column('profile', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('section_levels', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_ensembles_user_id', 'ensembles', ['user_id'])
    op.create_index('uq_ensembles_active', 'ensembles', ['user_id'], unique=True, postgresql_where=sa.text('is_active'))
    op.execute("""insert into ensembles (id, user_id, name, profile, section_levels, is_active, updated_at)
                  select gen_random_uuid(), user_id, 'Mi banda', profile, section_levels, true, updated_at from bands""")
    op.drop_table('bands')
    op.add_column('concerts', sa.Column('band_id', postgresql.UUID(as_uuid=True),
                                        sa.ForeignKey('ensembles.id', ondelete='SET NULL'), nullable=True))


def downgrade():
    op.drop_column('concerts', 'band_id')
    op.create_table('bands',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('profile', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('section_levels', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.execute("insert into bands (user_id, profile, section_levels, updated_at) "
               "select user_id, profile, section_levels, updated_at from ensembles where is_active")
    op.drop_index('uq_ensembles_active', table_name='ensembles')
    op.drop_index('ix_ensembles_user_id', table_name='ensembles')
    op.drop_table('ensembles')
