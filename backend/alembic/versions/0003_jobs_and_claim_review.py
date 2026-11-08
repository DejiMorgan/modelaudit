"""Nonblocking jobs and manual explanation-claim review
Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('experiments') as batch:
        batch.add_column(sa.Column('cancel_requested',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('explanation_claims',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('prediction_id',sa.String(),sa.ForeignKey('predictions.id'),nullable=False),
        sa.Column('claim_index',sa.Integer(),nullable=False),
        sa.Column('claim_text',sa.Text(),nullable=False),
        sa.Column('extraction_method',sa.String(32),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('prediction_id','claim_index'))
    op.create_index('ix_explanation_claims_prediction_id','explanation_claims',['prediction_id'])
    op.create_table('claim_judgments',
        sa.Column('id',sa.String(),primary_key=True),
        sa.Column('claim_id',sa.String(),sa.ForeignKey('explanation_claims.id'),nullable=False),
        sa.Column('judgment',sa.String(40),nullable=False),
        sa.Column('evidence_ids_json',sa.Text(),nullable=False),
        sa.Column('rationale',sa.Text(),nullable=False),
        sa.Column('annotation_source',sa.String(32),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_claim_judgments_claim_id','claim_judgments',['claim_id'])

def downgrade():
    op.drop_index('ix_claim_judgments_claim_id',table_name='claim_judgments')
    op.drop_table('claim_judgments')
    op.drop_index('ix_explanation_claims_prediction_id',table_name='explanation_claims')
    op.drop_table('explanation_claims')
    with op.batch_alter_table('experiments') as batch:
        batch.drop_column('cancel_requested')
