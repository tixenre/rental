"""equipo_mantenimiento: columnas para bloquear disponibilidad

Permite que un mantenimiento saque unidades del stock durante un rango:
- fecha_hasta: fin del bloqueo (NULL = solo log histórico, no bloquea)
- cantidad: cuántas unidades quedan fuera
- bloquea_stock: solo bloquea disponibilidad si es TRUE

Revision ID: c2f4a6b8e1d3
Revises: f5b8d2e4a9c1
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c2f4a6b8e1d3"
down_revision: Union[str, Sequence[str], None] = "f5b8d2e4a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS fecha_hasta TEXT")
    op.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS cantidad INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE equipo_mantenimiento ADD COLUMN IF NOT EXISTS bloquea_stock BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mantenimiento_bloqueo "
        "ON equipo_mantenimiento(equipo_id, fecha, fecha_hasta) WHERE bloquea_stock = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mantenimiento_bloqueo")
    op.execute("ALTER TABLE equipo_mantenimiento DROP COLUMN IF EXISTS bloquea_stock")
    op.execute("ALTER TABLE equipo_mantenimiento DROP COLUMN IF EXISTS cantidad")
    op.execute("ALTER TABLE equipo_mantenimiento DROP COLUMN IF EXISTS fecha_hasta")
