"""v0.1 baseline database schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('datasets',sa.Column('id',sa.String(),primary_key=True),sa.Column('name',sa.String(255),nullable=False),sa.Column('version',sa.String(80),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),sa.Column('row_count',sa.Integer(),nullable=False),sa.Column('source',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_datasets_sha256','datasets',['sha256'],unique=True)
    op.create_table('examples',sa.Column('id',sa.String(),primary_key=True),sa.Column('dataset_id',sa.String(),sa.ForeignKey('datasets.id'),nullable=False),sa.Column('external_id',sa.String(200),nullable=False),sa.Column('claim',sa.Text(),nullable=False),sa.Column('gold_label',sa.String(40),nullable=False),sa.Column('evidence_json',sa.Text(),nullable=False),sa.Column('gold_evidence_sets_json',sa.Text(),nullable=False),sa.Column('domain',sa.String(100),nullable=False),sa.UniqueConstraint('dataset_id','external_id'))
    op.create_index('ix_examples_dataset_id','examples',['dataset_id'])
    op.create_table('experiments',sa.Column('id',sa.String(),primary_key=True),sa.Column('name',sa.String(255),nullable=False),sa.Column('dataset_id',sa.String(),sa.ForeignKey('datasets.id'),nullable=False),sa.Column('adapter',sa.String(64),nullable=False),sa.Column('prompt_template',sa.Text(),nullable=False),sa.Column('prompt_hash',sa.String(64),nullable=False),sa.Column('seed',sa.Integer(),nullable=False),sa.Column('status',sa.String(32),nullable=False),sa.Column('error',sa.Text()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True)))
    op.create_table('predictions',sa.Column('id',sa.String(),primary_key=True),sa.Column('experiment_id',sa.String(),sa.ForeignKey('experiments.id'),nullable=False),sa.Column('example_id',sa.String(),sa.ForeignKey('examples.id'),nullable=False),sa.Column('predicted_label',sa.String(40)),sa.Column('explanation',sa.Text()),sa.Column('cited_evidence_json',sa.Text(),nullable=False),sa.Column('latency_ms',sa.Float()),sa.Column('status',sa.String(20),nullable=False),sa.Column('error',sa.Text()),sa.UniqueConstraint('experiment_id','example_id'))
    op.create_index('ix_predictions_experiment_id','predictions',['experiment_id'])

def downgrade():
    op.drop_index('ix_predictions_experiment_id',table_name='predictions');op.drop_table('predictions')
    op.drop_table('experiments');op.drop_index('ix_examples_dataset_id',table_name='examples');op.drop_table('examples')
    op.drop_index('ix_datasets_sha256',table_name='datasets');op.drop_table('datasets')
