"""Immutable experiment provenance snapshot
Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None
def upgrade():
    with op.batch_alter_table('experiments') as batch:
        batch.add_column(sa.Column('provenance_json',sa.Text(),nullable=False,server_default='{}'))
def downgrade():
    with op.batch_alter_table('experiments') as batch:
        batch.drop_column('provenance_json')
