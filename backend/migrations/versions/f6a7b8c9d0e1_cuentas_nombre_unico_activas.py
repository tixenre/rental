"""contabilidad: nombre de cuenta único solo entre activas (#809)

El nombre de una cuenta pasa a ser único SOLO entre las cuentas ACTIVAS. Antes el
único era global (`nombre TEXT UNIQUE`), así que una cuenta dada de baja (baja
lógica: `activa=FALSE`, la fila queda) seguía ocupando su nombre y bloqueaba
reusarlo (ej. no se podía renombrar "Fondo Rambla" a "Rambla - MercadoPago" si una
cuenta vieja con ese nombre estaba de baja). Se baja el único global y se crea uno
parcial `WHERE activa`.

Espejado en init_db() (esquema en dos capas, decisión 2026-06-03). Idempotente.

Revision ID: f6a7b8c9d0e1
Revises: y9z0a1b2c3d4
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "y9z0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # El único global de `nombre` (constraint implícita de TEXT UNIQUE) pasa a ser
    # un índice único PARCIAL sobre las activas → una cuenta de baja libera su nombre.
    bind.execute(sa.text("ALTER TABLE cuentas DROP CONSTRAINT IF EXISTS cuentas_nombre_key"))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS cuentas_nombre_activa_uq "
        "ON cuentas(nombre) WHERE activa"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS cuentas_nombre_activa_uq"))
    bind.execute(sa.text(
        "ALTER TABLE cuentas ADD CONSTRAINT cuentas_nombre_key UNIQUE (nombre)"
    ))
