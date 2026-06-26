"""trabajos: agregar categoría y descripción breve.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "estud3catdsc"
down_revision: Union[str, Sequence[str], None] = "estud2social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS categoria TEXT NOT NULL DEFAULT ''"
    ))
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS descripcion TEXT NOT NULL DEFAULT ''"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS categoria"))
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS descripcion"))
