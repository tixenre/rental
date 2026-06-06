"""pagos: destinatario (Tincho/Pablo) + metodo (transferencia/efectivo).

Suma dos columnas a `alquiler_pagos` para registrar a quién se cobró y cómo.
Parte de unificar el pago en una sola fuente de verdad (el ledger): #722.

Espeja `init_db()` (esquema en dos capas, `docs/MEMORIA.md` 2026-06-03): las
columnas se crean TAMBIÉN ahí con un ADD COLUMN idempotente. `ADD COLUMN IF NOT
EXISTS` hace esta migración segura aunque el bootstrap ya las haya agregado.

Backfill: los pagos **desde junio 2026** se asumen `Tincho` / `transferencia`
(decisión del dueño 2026-06-06). Los previos a junio son import del sistema
anterior → quedan NULL ("sin especificar") a propósito.

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "u5v6w7x8y9z0"
down_revision: Union[str, Sequence[str], None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS destinatario TEXT")
    op.execute("ALTER TABLE alquiler_pagos ADD COLUMN IF NOT EXISTS metodo TEXT")
    # Junio 2026 en adelante: asumir los defaults. Solo toca filas sin valor
    # (idempotente). Pre-junio queda NULL (import del sistema anterior).
    op.execute(
        "UPDATE alquiler_pagos "
        "SET destinatario = 'Tincho', metodo = 'transferencia' "
        "WHERE fecha >= '2026-06-01' AND destinatario IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquiler_pagos DROP COLUMN IF EXISTS metodo")
    op.execute("ALTER TABLE alquiler_pagos DROP COLUMN IF EXISTS destinatario")
