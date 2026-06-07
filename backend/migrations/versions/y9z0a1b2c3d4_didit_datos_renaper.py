"""Datos completos de RENAPER en clientes: nombre, apellido, fecha nacimiento, dirección, apodo.

Agrega 5 columnas a `clientes` para guardar los datos que RENAPER devuelve
a través de Didit al aprobar la verificación de identidad:
  - nombre_renaper         : nombre legal del DNI
  - apellido_renaper       : apellido legal del DNI
  - fecha_nacimiento_renaper: fecha de nacimiento (texto, formato del documento)
  - direccion_renaper      : domicilio legal del DNI
  - apodo                  : alias opcional para saludos informales en mails

Solo se persiste texto — no hay imagen ni biométrico (Ley 25.326).
Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03): `ADD COLUMN IF NOT
EXISTS` hace esta migración idempotente aunque el bootstrap ya las haya creado.

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "y9z0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "x8y9z0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nombre_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apellido_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS fecha_nacimiento_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS direccion_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apodo TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS apodo")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS direccion_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS fecha_nacimiento_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS apellido_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS nombre_renaper")
