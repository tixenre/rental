"""alquileres.descuento_cliente_pct: snapshot del descuento del cliente al
último recálculo (Fase C-1, #1219) — mismo patrón que descuento_jornadas_pct.

Sin esto, `desglose_de_pedido` tendría que leer `clientes.descuento` EN VIVO
para mostrar el desglose de un pedido ya confirmado — si el cliente cambia su
descuento después de confirmar, el desglose divergiría de `monto_total` ya
persistido (la clase de bug "dos cálculos del mismo número", #405).

Revision ID: n7o8p9q0r1s2
Revises: 6e8e632e32da
Create Date: 2026-07-03
"""
from typing import Sequence, Union
from alembic import op

revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, Sequence[str], None] = "6e8e632e32da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alquileres "
        "ADD COLUMN IF NOT EXISTS descuento_cliente_pct NUMERIC(5,2) DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquileres DROP COLUMN IF EXISTS descuento_cliente_pct")
