"""marcas: logo_url_sm para srcset del BrandCarousel (F4).

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2026-06-25
"""
from alembic import op

revision = "e4f5g6h7i8j9"
down_revision = "d3e4f5g6h7i8"  # F3: taller_inscripciones.comprobante_key
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE marcas ADD COLUMN IF NOT EXISTS logo_url_sm TEXT")


def downgrade():
    op.execute("ALTER TABLE marcas DROP COLUMN IF EXISTS logo_url_sm")
