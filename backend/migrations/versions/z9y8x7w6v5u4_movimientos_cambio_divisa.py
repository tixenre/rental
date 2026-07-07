"""movimientos: cotizacion + movimiento_par_id (cambio de divisa)

Comprar/vender USD con ARS no tenía un flujo soportado: `transferencia` exige
misma moneda en origen y destino (`_validar_cuentas_y_categoria`), así que una
conversión real entre cajas quedaba fuera de las reglas existentes — la
decisión 2026-06-07 ya anticipaba que "una conversión real entre cajas, si
hace falta, va como flujo aparte y explícito, no como edición de campo".

Se resuelve con DOS movimientos `ajuste` atados (uno por cada cuenta/moneda,
`commands/movimientos.py::crear_cambio_divisa`), no un tipo de movimiento
nuevo — no rompe la tabla tipo→cuentas del módulo. Dos columnas nuevas
soportan el par:

- `cotizacion`: pesos por dólar usados en la operación (informativo — se
  calcula solo si no se pasa; NO se recalcula después, es historia).
- `movimiento_par_id`: self-FK que linkea la pata ARS con la pata USD (se
  completa con un UPDATE después de insertar ambas filas — ninguna de las
  dos conoce el id de la otra al momento de insertarse).

Espeja init_db() (esquema en dos capas, MEMORIA 2026-06-03).

Revision ID: z9y8x7w6v5u4
Revises: q7r8s9t0u1v2
Create Date: 2026-07-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "z9y8x7w6v5u4"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS cotizacion NUMERIC(12,4)")
    op.execute(
        "ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS movimiento_par_id INTEGER "
        "REFERENCES movimientos(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE movimientos DROP COLUMN IF EXISTS movimiento_par_id")
    op.execute("ALTER TABLE movimientos DROP COLUMN IF EXISTS cotizacion")
