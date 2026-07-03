"""alquileres.descuento_pct: NUMERIC(5,2) → NUMERIC(7,4) — round-trip %/$ sin
perder precisión (Fase C-2, #1219).

El toggle %/$ del builder convierte el override manual al equivalente de la
otra unidad usando el desglose del backend (commit anterior de esta
iniciativa). Con solo 2 decimales, $50.000 sobre un bruto de $791.100
redondeaba a "6.32%" — y de ahí, volver a $ daba $49.998 (perdía ~$2 en el
redondeo intermedio). Con 4 decimales ("6.3202%") el redondeo intermedio
pierde centavos, no pesos — la ida y vuelta %→$→% queda prácticamente exacta
para cualquier bruto real. Solo afecta esta columna (el override manual, la
única que pasa por el toggle) — `descuento_jornadas_pct`/`descuento_cliente_pct`
no cambian: son snapshots de otra fuente, nunca se derivan de un $ manual.

Revision ID: w1x2y3z4a5b6
Revises: v9w0x1y2z3a4
Create Date: 2026-07-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, Sequence[str], None] = "v9w0x1y2z3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE alquileres ALTER COLUMN descuento_pct TYPE NUMERIC(7,4)")


def downgrade() -> None:
    op.execute("ALTER TABLE alquileres ALTER COLUMN descuento_pct TYPE NUMERIC(5,2)")
