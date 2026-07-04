"""facturas: nueva columna `domicilio` — congelado al emitir, no en vivo

El domicilio del receptor era el único de los 3 datos de facturación (junto
a razón social/CUIT) que NO quedaba fijo en la factura al emitir — se leía
en vivo de `clientes.domicilio_fiscal` en cada reimpresión del PDF. Si el
cliente editaba su domicilio después de facturado, una factura vieja podía
"cambiar" de domicilio retroactivamente.

Ahora, al emitir (`engine.py::emitir_factura`), el receptor se verifica
contra el padrón de ARCA y el domicilio que confirma AFIP queda persistido
en esta columna — igual que ya pasaba con `razon_social`. Nullable: las
facturas ya emitidas antes de esta migración quedan con `domicilio` NULL, y
`pdf.py` cae al valor en vivo de siempre para esas (backward-compatible, sin
backfill de datos históricos).

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: d4e6f8a2b1c3
Revises: w1x2y3z4a5b6
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e6f8a2b1c3"
down_revision: Union[str, Sequence[str], None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE facturas ADD COLUMN IF NOT EXISTS domicilio TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE facturas DROP COLUMN IF EXISTS domicilio")
