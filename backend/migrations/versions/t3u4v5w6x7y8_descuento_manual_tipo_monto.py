"""alquileres.descuento_manual_tipo/descuento_manual_monto: override manual en
% o en $ fijo (Fase C-2, #1219).

`descuento_manual_tipo` decide cómo se interpreta el override del pedido —
'pct' (de siempre, usa `descuento_pct`) o 'monto' (usa
`descuento_manual_monto`, pesos fijos, capeado a `bruto`). Default 'pct' +
monto=0 → comportamiento IDÉNTICO al de antes de C-2.

Revision ID: t3u4v5w6x7y8
Revises: n7o8p9q0r1s2
Create Date: 2026-07-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "t3u4v5w6x7y8"
down_revision: Union[str, Sequence[str], None] = "n7o8p9q0r1s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alquileres "
        "ADD COLUMN IF NOT EXISTS descuento_manual_tipo VARCHAR(10) DEFAULT 'pct'"
    )
    op.execute(
        "ALTER TABLE alquileres "
        "ADD COLUMN IF NOT EXISTS descuento_manual_monto INTEGER DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquileres DROP COLUMN IF EXISTS descuento_manual_monto")
    op.execute("ALTER TABLE alquileres DROP COLUMN IF EXISTS descuento_manual_tipo")
