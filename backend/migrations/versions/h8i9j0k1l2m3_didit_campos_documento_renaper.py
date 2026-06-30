"""Datos adicionales del documento RENAPER: género, nacionalidad, lugar nacimiento, etc.

Agrega 7 columnas a `clientes` con los campos del documento que Didit/RENAPER
devuelve en `id_verifications[]` (API v3) y que antes no se guardaban:
  - genero_renaper          : "M" / "F"
  - nacionalidad_renaper    : código de país ("ARG")
  - lugar_nacimiento_renaper: ciudad/provincia de nacimiento
  - vencimiento_documento_renaper: fecha de vencimiento del DNI
  - emision_documento_renaper    : fecha de emisión del DNI
  - tipo_documento_renaper  : "Identity Card" / "Passport"
  - estado_civil_renaper    : "Single" / "Married" / etc.

Solo texto — no hay imagen ni biométrico (Ley 25.326).
Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS genero_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nacionalidad_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS lugar_nacimiento_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS vencimiento_documento_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS emision_documento_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS tipo_documento_renaper TEXT")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS estado_civil_renaper TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS estado_civil_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS tipo_documento_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS emision_documento_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS vencimiento_documento_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS lugar_nacimiento_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS nacionalidad_renaper")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS genero_renaper")
