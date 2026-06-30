"""trabajos: agregar links_json (lista ordenada de medios externos).

Revision ID: b8742ce91a07
Revises: a7637d890516
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8742ce91a07"
down_revision: Union[str, Sequence[str], None] = "a7637d890516"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio_trabajos "
        "ADD COLUMN IF NOT EXISTS links_json TEXT NOT NULL DEFAULT '[]'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio_trabajos DROP COLUMN IF EXISTS links_json"))
