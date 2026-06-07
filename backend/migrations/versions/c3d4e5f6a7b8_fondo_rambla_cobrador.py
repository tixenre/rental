"""contabilidad: Fondo Rambla representa al cobrador 'Rambla' (#809)

Ahora Rambla también puede cobrar pagos de cliente (default en transferencia). La
plata que cobra Rambla se atribuye a la caja Fondo Rambla, igual que Pablo/Tincho
a su caja de socio — el puente es la columna `cuentas.socio` (el cobrador que la
caja representa). Backfilleamos las cajas Fondo Rambla existentes con socio='Rambla'.

Espejado en init_db() (esquema en dos capas). Idempotente.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE cuentas SET socio = 'Rambla' WHERE nombre = 'Fondo Rambla' AND socio IS NULL"
    ))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE cuentas SET socio = NULL WHERE nombre = 'Fondo Rambla' AND socio = 'Rambla'"
    ))
