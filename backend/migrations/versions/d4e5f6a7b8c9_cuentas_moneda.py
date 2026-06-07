"""contabilidad: moneda por cuenta (ARS/USD) + caja en dólares (#809)

Una caja puede ser en pesos (ARS, default) o en dólares (USD) — a veces se guardan
dólares. Cada caja tiene su moneda; los saldos NO se mezclan entre monedas (el
tablero los muestra por separado) y las transferencias deben ser de la misma
moneda. Los cobros de clientes son en ARS (solo alimentan cajas ARS).

Espejado en init_db() (esquema en dos capas). Idempotente.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS moneda VARCHAR(3) NOT NULL DEFAULT 'ARS'"
    ))
    bind.execute(sa.text(
        "INSERT INTO cuentas (nombre, tipo, moneda, orden) "
        "VALUES ('Dólares', 'caja', 'USD', 6) ON CONFLICT (nombre) WHERE activa DO NOTHING"
    ))


def downgrade() -> None:
    op.get_bind().execute(sa.text("ALTER TABLE cuentas DROP COLUMN IF EXISTS moneda"))
