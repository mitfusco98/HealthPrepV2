"""Add living document columns for prep sheet limits and supersession

Revision ID: a1b2c3d4e5f6
Revises: fdf5ccf0e67b
Create Date: 2026-01-23 04:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'fdf5ccf0e67b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('patient', sa.Column('prep_sheet_count_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('patient', sa.Column('prep_sheet_count_date', sa.Date(), nullable=True))
    op.add_column('patient', sa.Column('last_prep_sheet_epic_id', sa.String(100), nullable=True))
    op.add_column('fhir_documents', sa.Column('is_superseded', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('fhir_documents', 'is_superseded')
    op.drop_column('patient', 'last_prep_sheet_epic_id')
    op.drop_column('patient', 'prep_sheet_count_date')
    op.drop_column('patient', 'prep_sheet_count_today')
