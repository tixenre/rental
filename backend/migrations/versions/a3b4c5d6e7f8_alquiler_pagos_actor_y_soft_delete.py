"""alquiler_pagos: actor (created_by) + soft-delete con motivo (auditoría #1184)

Suma el mismo patrón anulado/anulado_por/anulado_at/anulado_motivo que ya usa
`movimientos` (#809) a `alquiler_pagos` — la tabla que ALIMENTA todo el motor
de contabilidad (ingresos_derivados, saldos, rendicion, reporte_mensual) no
respetaba "la plata no se borra": `eliminar_pago` hacía un DELETE real, sin
motivo, sin registrar quién. `created_by` captura quién cargó el cobro.

Espeja init_db() (esquema en dos capas, decisión 2026-06-03). `ADD COLUMN IF
NOT EXISTS` es idempotente.

Revision ID: a3b4c5d6e7f8
Revises: e111286012ff
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "e111286012ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS created_by TEXT")
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS anulado BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS anulado_por TEXT")
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS anulado_at TIMESTAMP")
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS anulado_motivo TEXT")


def downgrade() -> None:
    for col in ("anulado_motivo", "anulado_at", "anulado_por", "anulado", "created_by"):
        op.execute(f"ALTER TABLE alquiler_pagos DROP COLUMN IF EXISTS {col}")
