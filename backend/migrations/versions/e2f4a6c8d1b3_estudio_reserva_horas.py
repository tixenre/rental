"""estudio E2: reserva por horas — tipo/estudio_con_pack en alquileres + recurso interno.

Revision ID: e2f4a6c8d1b3
Revises: c1d3e5f7a9b2
Create Date: 2026-05-27

Schema para la reserva del Estudio por horas (E2):
- `alquileres.tipo` ('diaria' por default → cero impacto en reservas/queries
  existentes; 'estudio' marca las reservas del espacio por hora).
- `alquileres.estudio_con_pack` (reservado para E3 — pack Grip/Luz).
- `equipos.es_recurso_interno` (el centinela del Estudio: un equipo de
  cantidad=1 invisible al catálogo/listados/ranking/specs, sembrado por init_db).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f4a6c8d1b3"
down_revision: Union[str, Sequence[str], None] = "c1d3e5f7a9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'diaria'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS estudio_con_pack BOOLEAN NOT NULL DEFAULT FALSE"
    ))
    conn.execute(sa.text(
        "ALTER TABLE equipos ADD COLUMN IF NOT EXISTS es_recurso_interno BOOLEAN NOT NULL DEFAULT FALSE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE equipos DROP COLUMN IF EXISTS es_recurso_interno"))
    conn.execute(sa.text("ALTER TABLE alquileres DROP COLUMN IF EXISTS estudio_con_pack"))
    conn.execute(sa.text("ALTER TABLE alquileres DROP COLUMN IF EXISTS tipo"))
