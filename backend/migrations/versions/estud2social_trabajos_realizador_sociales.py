"""trabajos: agregar instagram y web del realizador.

Campos opcionales — si están vacíos no se muestran en la página pública.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "estud2social"
down_revision: Union[str, Sequence[str], None] = "estud1trabaj"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS realizador_instagram TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos ADD COLUMN IF NOT EXISTS realizador_web TEXT"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS realizador_instagram"))
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS realizador_web"))
