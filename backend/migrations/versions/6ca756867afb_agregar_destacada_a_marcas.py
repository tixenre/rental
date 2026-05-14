"""agregar destacada a marcas

Issue #288: curación manual de marcas destacadas en el catálogo público.

Hoy el BrandCarousel del home elige top N marcas por count de equipos
automáticamente. Esta migración agrega un flag `destacada` para que el
admin pueda override la curación manualmente (ej. destacar DJI por una
campaña aunque tenga menos equipos que Sony).

Comportamiento del frontend:
- Si hay al menos 1 marca con `destacada=true` → mostrar solo esas.
- Si ninguna está marcada → fallback al algoritmo automático (top N).

Revision ID: 6ca756867afb
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "6ca756867afb"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE marcas "
        "ADD COLUMN IF NOT EXISTS destacada BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    pass
