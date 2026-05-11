"""agregar popularidad_score y cant_pedidos a marcas y categorias

Issue #131: extender el sistema de ranking automático (#124) a marcas
y categorías. Hoy solo aplica a equipos. Después de esta migración,
el recálculo también ordena marcas en el carrusel y categorías en el
mosaico por uso real (pedidos + ingresos), no solo por el campo manual.

El campo `orden` (marcas) y `prioridad` (categorias) sigue existiendo
como override manual — equivalente a `relevancia_manual` en equipos.

Revision ID: 091de6e7b201
Revises: c47b6b4e2851
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "091de6e7b201"
down_revision: Union[str, Sequence[str], None] = "c47b6b4e2851"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Marcas
    op.execute(
        "ALTER TABLE marcas ADD COLUMN IF NOT EXISTS popularidad_score INT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE marcas ADD COLUMN IF NOT EXISTS cant_pedidos INT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE marcas ADD COLUMN IF NOT EXISTS ingreso_total_ars BIGINT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE marcas ADD COLUMN IF NOT EXISTS ranking_actualizado TIMESTAMP"
    )

    # Categorías
    op.execute(
        "ALTER TABLE categorias ADD COLUMN IF NOT EXISTS popularidad_score INT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE categorias ADD COLUMN IF NOT EXISTS cant_pedidos INT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE categorias ADD COLUMN IF NOT EXISTS ingreso_total_ars BIGINT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE categorias ADD COLUMN IF NOT EXISTS ranking_actualizado TIMESTAMP"
    )


def downgrade() -> None:
    """No-op: las columnas no afectan funcionalidad existente. Si se quieren
    sacar, hacer drop_column individual aquí."""
    pass
