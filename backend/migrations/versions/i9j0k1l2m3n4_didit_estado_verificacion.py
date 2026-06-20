"""Estado de verificación Didit: dni_verificacion_estado + dni_verificacion_motivo.

Agrega 2 columnas a `clientes` para rastrear el estado completo del flujo Didit,
más allá del binario `dni_validado_at IS NULL/NOT NULL`:

  - dni_verificacion_estado: 'no_verificado' (default), 'verificado', 'rechazado',
    'en_revision'. Actualizado por el webhook en cada evento de Didit.
  - dni_verificacion_motivo: razón textual del rechazo o revisión (TEXT, NULL si
    no aplica). Solo texto — Ley 25.326.

El criterio de gate de pedidos sigue siendo `dni_validado_at IS NOT NULL` (fuente
única, sin cambio). Este campo añade visibilidad de estados intermedios para el
portal del cliente (ej. "Tu verificación fue rechazada — podés reintentarla").

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS "
        "dni_verificacion_estado TEXT NOT NULL DEFAULT 'no_verificado'"
    )
    op.execute(
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS "
        "dni_verificacion_motivo TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS dni_verificacion_motivo")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS dni_verificacion_estado")
