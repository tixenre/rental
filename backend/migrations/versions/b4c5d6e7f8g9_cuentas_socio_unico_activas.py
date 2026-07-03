"""contabilidad: idx_cuentas_socio único solo entre activas (auditoría #1184)

Simétrico con `cuentas_nombre_activa_uq` (migración f6a7b8c9d0e1): antes
`idx_cuentas_socio` era único sobre TODAS las filas (activas e inactivas), así
que dar de baja una cuenta de socio (ej. "Caja Pablo") bloqueaba para siempre
crear una nueva cuenta ACTIVA con `socio='Pablo'` — la fila vieja inactiva
seguía ocupando el slot único. Se baja el índice viejo y se crea uno parcial
`WHERE socio IS NOT NULL AND activa`.

El target-less `ON CONFLICT DO NOTHING` del seed de cuentas en `init_db()`
(#932) sigue siendo necesario igual — cubre el caso de una cuenta ACTIVA
renombrada que conserva su `socio`, agnóstico de cuál de los dos índices
únicos la atrape.

Espejado en init_db() (esquema en dos capas, decisión 2026-06-03). Idempotente.

Revision ID: b4c5d6e7f8g9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8g9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_cuentas_socio"))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cuentas_socio "
        "ON cuentas(socio) WHERE socio IS NOT NULL AND activa"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_cuentas_socio"))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cuentas_socio "
        "ON cuentas(socio) WHERE socio IS NOT NULL"
    ))
