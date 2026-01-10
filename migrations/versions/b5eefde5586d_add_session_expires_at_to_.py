"""Add session_expires_at to EpicCredentials and Provider models

Revision ID: b5eefde5586d
Revises: 
Create Date: 2026-01-10 19:03:35.153606

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b5eefde5586d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add session_expires_at column to epic_credentials table
    with op.batch_alter_table('epic_credentials', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_expires_at', sa.DateTime(), nullable=True))

    # Add session_expires_at column to providers table
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('providers', schema=None) as batch_op:
        batch_op.drop_column('session_expires_at')

    with op.batch_alter_table('epic_credentials', schema=None) as batch_op:
        batch_op.drop_column('session_expires_at')
