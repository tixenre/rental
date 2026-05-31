"""A1 #635: campo tipo en equipos + columnas de fases siguientes en kit_componentes.

Dimension de clasificación: tipo (simple/kit/combo) gobierna precio, stock y
disponibilidad. Backfill seguro: sin componentes → 'simple'; con componentes
→ 'kit' (los Combo se marcan a mano después, cuando exista la categoría Combos).

Columnas para fases C:
- kit_componentes.descuento_pct (FLOAT DEFAULT 0): descuento % por línea de combo.
- kit_componentes.esencial (BOOLEAN DEFAULT TRUE): False = best-effort (patrón Estudio).

Revision ID: a1c3b5f7e9d2
Revises: b1e3f5a7c9d2
Create Date: 2026-05-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3b5f7e9d2"
down_revision: Union[str, Sequence[str], None] = "b1e3f5a7c9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Columna tipo en equipos — DEFAULT 'simple' para backfill seguro
    conn.execute(sa.text(
        "ALTER TABLE equipos ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'simple'"
    ))

    # 2. Backfill: equipos con kit_componentes ya cargados → 'kit'
    conn.execute(sa.text(
        "UPDATE equipos SET tipo = 'kit' "
        "WHERE tipo = 'simple' "
        "  AND id IN (SELECT DISTINCT equipo_id FROM kit_componentes)"
    ))

    # 3. CHECK constraint (después del backfill para no violar durante la migración)
    conn.execute(sa.text(
        "ALTER TABLE equipos DROP CONSTRAINT IF EXISTS equipos_tipo_check"
    ))
    conn.execute(sa.text(
        "ALTER TABLE equipos ADD CONSTRAINT equipos_tipo_check "
        "CHECK (tipo IN ('simple', 'kit', 'combo'))"
    ))

    # 4. descuento_pct en kit_componentes (para combos — C3)
    conn.execute(sa.text(
        "ALTER TABLE kit_componentes "
        "ADD COLUMN IF NOT EXISTS descuento_pct FLOAT NOT NULL DEFAULT 0.0"
    ))

    # 5. esencial en kit_componentes (para best-effort — C2)
    conn.execute(sa.text(
        "ALTER TABLE kit_componentes "
        "ADD COLUMN IF NOT EXISTS esencial BOOLEAN NOT NULL DEFAULT TRUE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE equipos DROP CONSTRAINT IF EXISTS equipos_tipo_check"
    ))
    conn.execute(sa.text("ALTER TABLE equipos DROP COLUMN IF EXISTS tipo"))
    conn.execute(sa.text("ALTER TABLE kit_componentes DROP COLUMN IF EXISTS descuento_pct"))
    conn.execute(sa.text("ALTER TABLE kit_componentes DROP COLUMN IF EXISTS esencial"))
