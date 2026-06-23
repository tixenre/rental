"""talleres: numero_edicion y proxima_edicion_slug para multi-edición

Permite vincular ediciones del mismo workshop (ej. julio → agosto).
ADD COLUMN IF NOT EXISTS = idempotente.

Revision ID: t4ll3r3d1c1x1
Revises: t3ll4r1nst4x1
Create Date: 2026-06-23
"""
from alembic import op

revision = "t4ll3r3d1c1x1"
down_revision = "t3ll4r1nst4x1"
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
