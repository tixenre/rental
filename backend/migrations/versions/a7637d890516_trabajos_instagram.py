"""trabajos: agregar instagram_reel_url y thumbnail_url.

Revision ID: a7637d890516
Revises: c3d4e5f6a7b8
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7637d890516"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS instagram_reel_url TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS thumbnail_url TEXT"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS instagram_reel_url"))
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS thumbnail_url"))
