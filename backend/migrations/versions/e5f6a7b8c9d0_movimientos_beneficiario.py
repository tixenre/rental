"""contabilidad: beneficiario en movimientos (a quién / para qué es el gasto) (#809)

Campo libre pero PARSEABLE y reutilizable: a quién es el gasto (ej. "Jimena"). La
UI ofrece autocompletado con los beneficiarios ya usados, así no se reescribe cada
vez y se puede ver el historial por beneficiario. No es un sistema de empleados —
es solo una etiqueta de texto sobre el movimiento.

Espejado en init_db() (esquema en dos capas). Idempotente.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS beneficiario TEXT"
    ))


def downgrade() -> None:
    op.get_bind().execute(sa.text("ALTER TABLE movimientos DROP COLUMN IF EXISTS beneficiario"))
