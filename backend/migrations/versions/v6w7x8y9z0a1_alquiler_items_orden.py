"""alquiler_items_orden: orden manual de líneas del pedido (drag-reorder, #806).

Agrega `alquiler_items.orden INTEGER NOT NULL DEFAULT 0` para persistir el orden
manual de las líneas de un pedido (reordenar arrastrando en el back-office). Los
displays (detalle admin, portal, PDFs) ordenan por `orden, id`; el valor se
asigna por posición al guardar los ítems.

Espeja `init_db()` (esquema en dos capas, `docs/MEMORIA.md` 2026-06-03): la
columna se crea TAMBIÉN ahí con un ADD COLUMN idempotente. `ADD COLUMN IF NOT
EXISTS` hace esta migración segura aunque el bootstrap ya la haya agregado.

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "v6w7x8y9z0a1"
down_revision: Union[str, Sequence[str], None] = "u5v6w7x8y9z0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alquiler_items "
        "ADD COLUMN IF NOT EXISTS orden INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquiler_items DROP COLUMN IF EXISTS orden")
