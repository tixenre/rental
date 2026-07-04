"""alquileres.descuento_manual_activo: forzar el override manual a ganar
OUTRIGHT aunque valga 0 (Fase C-4, #1231).

Bug real reportado: `descuento_pct=0`/`descuento_manual_monto=0` es el
sentinel de "sin override" — indistinguible de "quiero 0% en ESTE pedido
puntual". Un pedido cuyo `descuento_cliente_pct` quedó congelado en un valor
>0 (ej. por el backfill de `v9w0x1y2z3a4`, que no podía distinguir un
descuento del cliente de una edición manual histórica) no tenía forma de
corregirse desde la UI: cualquier valor "0" tipeado en el override caía al
mismo fallback cliente/jornadas. `descuento_manual_activo=TRUE` + el override
en 0 ahora gana outright, exactamente igual que cualquier otro valor manual.

Default FALSE → comportamiento IDÉNTICO al de antes para el 100% de los
pedidos existentes.

Revision ID: j2k3l4m5n6o7
Revises: d4e6f8a2b1c3
Create Date: 2026-07-04
"""
from typing import Sequence, Union
from alembic import op

revision: str = "j2k3l4m5n6o7"
down_revision: Union[str, Sequence[str], None] = "d4e6f8a2b1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alquileres "
        "ADD COLUMN IF NOT EXISTS descuento_manual_activo BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquileres DROP COLUMN IF EXISTS descuento_manual_activo")
