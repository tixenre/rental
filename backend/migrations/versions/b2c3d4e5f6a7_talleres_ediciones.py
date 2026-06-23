"""talleres: numero_edicion y proxima_edicion_slug para multi-edición

Permite vincular ediciones del mismo workshop (ej. julio → agosto).
ADD COLUMN IF NOT EXISTS = idempotente.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-23
"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE talleres
        ADD COLUMN IF NOT EXISTS numero_edicion INTEGER NOT NULL DEFAULT 1,
        ADD COLUMN IF NOT EXISTS proxima_edicion_slug TEXT NOT NULL DEFAULT ''
    """)


def downgrade():
    op.execute("""
        ALTER TABLE talleres
        DROP COLUMN IF EXISTS numero_edicion,
        DROP COLUMN IF EXISTS proxima_edicion_slug
    """)
