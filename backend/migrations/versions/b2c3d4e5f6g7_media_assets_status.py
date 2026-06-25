"""media_assets: columna status (pending/ready/failed) para derivación en background (F0g).

Merja además la rama media (v1w2x3y4z5a6, lqip) con la rama principal
(z0a1b2c3d4e5, didit-identidad) que divergieron en dev.

Revision ID: b2c3d4e5f6g7
Revises: z0a1b2c3d4e5, v1w2x3y4z5a6
Create Date: 2026-06-25
"""
from alembic import op

revision = "b2c3d4e5f6g7"
down_revision = ("z0a1b2c3d4e5", "v1w2x3y4z5a6")
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS "
        "status TEXT NOT NULL DEFAULT 'ready'"
    )


def downgrade():
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS status")
