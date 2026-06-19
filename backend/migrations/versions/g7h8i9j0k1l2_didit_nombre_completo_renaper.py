"""Nombre legal completo de RENAPER en clientes (para contratos).

Agrega `nombre_completo_renaper` a `clientes`: el nombre legal tal cual lo
devuelve RENAPER (`full_name`), sin reconstruirlo de nombre+apellido. Importa
para los contratos, donde el string legal exacto (orden, segundos nombres,
apellidos compuestos) cuenta.

Solo texto — no hay imagen ni biométrico (Ley 25.326).
Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03): `ADD COLUMN IF NOT
EXISTS` hace esta migración idempotente aunque el bootstrap ya la haya creado.

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nombre_completo_renaper TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS nombre_completo_renaper")
