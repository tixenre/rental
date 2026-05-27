"""estudio E4: slots fijos recurrentes mensuales.

Revision ID: a4c8e2f6b1d9
Revises: f3a7b9d2c4e6
Create Date: 2026-05-27

Tabla `estudio_slots_fijos` (usos recurrentes mensuales del estudio que bloquean
su franja y generan un pedido por mes) + `alquileres.estudio_slot_id` para
vincular los pedidos mensuales generados con su slot.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e2f6b1d9"
down_revision: Union[str, Sequence[str], None] = "f3a7b9d2c4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS estudio_slots_fijos (
            id            SERIAL PRIMARY KEY,
            cliente       TEXT NOT NULL,
            dia_semana    INTEGER NOT NULL,
            hora_desde    INTEGER NOT NULL,
            hora_hasta    INTEGER NOT NULL,
            valor_mensual INTEGER NOT NULL DEFAULT 0,
            mes_desde     TEXT NOT NULL,
            mes_hasta     TEXT NOT NULL,
            activo        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS estudio_slot_id INTEGER "
        "REFERENCES estudio_slots_fijos(id) ON DELETE SET NULL"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE alquileres DROP COLUMN IF EXISTS estudio_slot_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS estudio_slots_fijos"))
