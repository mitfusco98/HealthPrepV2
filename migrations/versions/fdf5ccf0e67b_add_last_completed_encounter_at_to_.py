"""Add last_completed_encounter_at to patient table

Revision ID: fdf5ccf0e67b
Revises: b5eefde5586d
Create Date: 2026-01-13 16:19:03.584373

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fdf5ccf0e67b'
down_revision = 'b5eefde5586d'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_completed_encounter_at column to patient table
    # This stores the most recent completed encounter before today for "To Last Encounter" prep sheet cutoffs
    op.add_column('patient', sa.Column('last_completed_encounter_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('patient', 'last_completed_encounter_at')
