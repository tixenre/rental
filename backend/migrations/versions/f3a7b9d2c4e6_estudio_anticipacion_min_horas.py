"""estudio E2.1: anticipación mínima de reserva (horas).

Revision ID: f3a7b9d2c4e6
Revises: e2f4a6c8d1b3
Create Date: 2026-05-27

Agrega `estudio.anticipacion_min_horas` (INTEGER DEFAULT 0): horas mínimas de
anticipación con las que se puede reservar el espacio del estudio. Solo aplica
al estudio (no a los equipos). 0 = sin tope.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a7b9d2c4e6"
down_revision: Union[str, Sequence[str], None] = "e2f4a6c8d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE estudio ADD COLUMN IF NOT EXISTS anticipacion_min_horas INTEGER NOT NULL DEFAULT 0"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE estudio DROP COLUMN IF EXISTS anticipacion_min_horas"))
