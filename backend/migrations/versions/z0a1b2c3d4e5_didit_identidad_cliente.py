"""Verificación de identidad Didit: columnas en clientes.

Agrega 4 columnas a `clientes` para registrar el resultado de la validación
DNI + selfie contra RENAPER vía Didit:
  - dni             : número de documento validado (sin foto)
  - cuil            : CUIL personal confirmado (puede diferir del cuit de facturación)
  - dni_validado_at : timestamp de la aprobación Didit (NULL = pendiente)
  - didit_session_id: ID de sesión para auditoría y trazabilidad

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03): `ADD COLUMN IF NOT
EXISTS` hace esta migración idempotente aunque el bootstrap ya las haya creado.

Revision ID: z0a1b2c3d4e5
Revises: w7x8y9z0a1b2
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "z0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "w7x8y9z0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS dni TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cuil TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS dni_validado_at TIMESTAMP")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS didit_session_id TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS didit_session_id")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS dni_validado_at")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS cuil")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS dni")
