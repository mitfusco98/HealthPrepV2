"""Add page_count and skipped_oversized columns to FHIRDocument

COST CONTROL: These columns track document page counts and identify
oversized documents that were skipped to prevent runaway OCR costs.

Revision ID: c2d3e4f5g6h7
Revises: fdf5ccf0e67b
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2d3e4f5g6h7'
down_revision = 'fdf5ccf0e67b'
branch_labels = None
depends_on = None


def upgrade():
    # Add page_count column for tracking document page counts
    op.add_column('fhir_documents', sa.Column('page_count', sa.Integer(), nullable=True))
    
    # Add skipped_oversized flag for cost control tracking
    op.add_column('fhir_documents', sa.Column('skipped_oversized', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('fhir_documents', 'skipped_oversized')
    op.drop_column('fhir_documents', 'page_count')
