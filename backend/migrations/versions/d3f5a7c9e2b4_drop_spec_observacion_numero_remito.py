"""normalizacion: drop spec_observacion (tabla muerta) + numero_remito (redundante)

- spec_observacion: el feature "observatorio de specs" fue removido (no hay
  ruta backend ni uso en el frontend). La tabla quedaba huerfana.
- alquileres.numero_remito: siempre == numero_pedido. Redundante. Los PDFs,
  busqueda y orden ya usan numero_pedido.

Revision ID: d3f5a7c9e2b4
Revises: c2f4a6b8e1d3
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d3f5a7c9e2b4"
down_revision: Union[str, Sequence[str], None] = "c2f4a6b8e1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS spec_observacion")
    op.execute("ALTER TABLE alquileres DROP COLUMN IF EXISTS numero_remito")


def downgrade() -> None:
    op.execute("ALTER TABLE alquileres ADD COLUMN IF NOT EXISTS numero_remito TEXT")
    # spec_observacion no se recrea (feature removido).
