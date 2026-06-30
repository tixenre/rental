"""trabajos: agregar categorias_json (varios tags por trabajo).

Revision ID: c9853df02b18
Revises: b8742ce91a07
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9853df02b18"
down_revision: Union[str, Sequence[str], None] = "b8742ce91a07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos "
        "ADD COLUMN IF NOT EXISTS categorias_json TEXT NOT NULL DEFAULT '[]'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS categorias_json"))
