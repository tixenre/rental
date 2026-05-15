"""metadata para compatibilidades auto-generadas por IA

Distingue compat manuales (ingresadas por el dueño) de las que genera el
skill `/compat`. Las auto se borran y regeneran en cada pasada del skill,
las manuales nunca se tocan.

Revision ID: b2d4f6a8c1e3
Revises: f9a3c5d8b1e7
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b2d4f6a8c1e3"
down_revision: Union[str, Sequence[str], None] = "f9a3c5d8b1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE equipo_compatibilidad "
        "ADD COLUMN IF NOT EXISTS auto_generado BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE equipo_compatibilidad "
        "ADD COLUMN IF NOT EXISTS razon_ia TEXT"
    )
    op.execute(
        "ALTER TABLE equipo_compatibilidad "
        "ADD COLUMN IF NOT EXISTS confianza REAL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_compat_auto "
        "ON equipo_compatibilidad(auto_generado) WHERE auto_generado = TRUE"
    )
    op.execute(
        "ALTER TABLE equipos "
        "ADD COLUMN IF NOT EXISTS compat_analizado_at TIMESTAMP"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS compat_analizado_at")
    op.execute("DROP INDEX IF EXISTS idx_compat_auto")
    op.execute("ALTER TABLE equipo_compatibilidad DROP COLUMN IF EXISTS confianza")
    op.execute("ALTER TABLE equipo_compatibilidad DROP COLUMN IF EXISTS razon_ia")
    op.execute("ALTER TABLE equipo_compatibilidad DROP COLUMN IF EXISTS auto_generado")
