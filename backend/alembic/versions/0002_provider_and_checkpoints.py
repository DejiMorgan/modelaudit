"""External provider configuration and checkpoint metadata
Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('experiments') as batch:
        batch.add_column(sa.Column('model_identifier',sa.String(200),nullable=False,server_default='mock'))
        batch.add_column(sa.Column('parameters_json',sa.Text(),nullable=False,server_default='{}'))
        batch.add_column(sa.Column('started_at',sa.DateTime(timezone=True),nullable=True))
    with op.batch_alter_table('predictions') as batch:
        batch.add_column(sa.Column('raw_response_json',sa.Text(),nullable=True))
        batch.add_column(sa.Column('input_tokens',sa.Integer(),nullable=True))
        batch.add_column(sa.Column('output_tokens',sa.Integer(),nullable=True))

def downgrade():
    with op.batch_alter_table('predictions') as batch:
        batch.drop_column('output_tokens');batch.drop_column('input_tokens');batch.drop_column('raw_response_json')
    with op.batch_alter_table('experiments') as batch:
        batch.drop_column('started_at');batch.drop_column('parameters_json');batch.drop_column('model_identifier')
