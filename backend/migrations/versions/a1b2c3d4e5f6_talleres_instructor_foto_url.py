"""talleres: agregar instructor_foto_url (URL pública de la foto de la instructora)

La columna va también en init_db() (esquema en dos capas, MEMORIA 2026-06-03).
ADD COLUMN IF NOT EXISTS hace la migración idempotente. La URL queda vacía hasta
que se suba la foto y se actualice la fila en la DB.

Revision ID: a1b2c3d4e5f6
Revises: s1r2c3s4e5t6
Create Date: 2026-06-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "s1r2c3s4e5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE talleres ADD COLUMN IF NOT EXISTS instructor_foto_url TEXT NOT NULL DEFAULT ''"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE talleres DROP COLUMN IF EXISTS instructor_foto_url"))
