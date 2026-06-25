"""taller_inscripciones: comprobante_key para almacenamiento privado (F3).

Revision ID: d3e4f5g6h7i8
Revises: b2c3d4e5f6g7
Create Date: 2026-06-25
"""
from alembic import op

revision = "d3e4f5g6h7i8"
down_revision = "c2d3e4f5g6h7"  # F2: talleres.instructor_media_id
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE taller_inscripciones ADD COLUMN IF NOT EXISTS comprobante_key TEXT"
    )


def downgrade():
    op.execute(
        "ALTER TABLE taller_inscripciones DROP COLUMN IF EXISTS comprobante_key"
    )
