"""talleres: instructor_media_id → media_assets (F2).

Revision ID: c2d3e4f5g6h7
Revises: b2c3d4e5f6g7
Create Date: 2026-06-25
"""
from alembic import op

revision = "c2d3e4f5g6h7"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE talleres ADD COLUMN IF NOT EXISTS "
        "instructor_media_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL"
    )


def downgrade():
    op.execute("ALTER TABLE talleres DROP COLUMN IF EXISTS instructor_media_id")
