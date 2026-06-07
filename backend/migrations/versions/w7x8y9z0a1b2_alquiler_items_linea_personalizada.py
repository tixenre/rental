"""alquiler_items_linea_personalizada: líneas de texto libre en el pedido (#805).

Habilita las "líneas personalizadas": ítems de un pedido que NO son del catálogo
(flete, operador, limpieza, etc.). Cambios:
- `equipo_id` deja de ser NOT NULL → una línea con `equipo_id IS NULL` es libre y
  NO reserva stock (el motor de reservas la excluye).
- `nombre_libre TEXT` → nombre de la línea libre.
- `cobro_modo TEXT NOT NULL DEFAULT 'jornada'` → 'jornada' (× jornadas, como los
  equipos) | 'fijo' (monto único, sin multiplicar por jornadas).

Espeja `init_db()` (esquema en dos capas, `docs/MEMORIA.md` 2026-06-03): los mismos
cambios se aplican TAMBIÉN ahí, idempotentes. `IF NOT EXISTS` / `DROP NOT NULL`
hacen esta migración segura aunque el bootstrap ya los haya aplicado.

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "w7x8y9z0a1b2"
down_revision: Union[str, Sequence[str], None] = "v6w7x8y9z0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE alquiler_items ALTER COLUMN equipo_id DROP NOT NULL")
    op.execute("ALTER TABLE alquiler_items ADD COLUMN IF NOT EXISTS nombre_libre TEXT")
    op.execute(
        "ALTER TABLE alquiler_items "
        "ADD COLUMN IF NOT EXISTS cobro_modo TEXT NOT NULL DEFAULT 'jornada'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE alquiler_items DROP COLUMN IF EXISTS cobro_modo")
    op.execute("ALTER TABLE alquiler_items DROP COLUMN IF EXISTS nombre_libre")
    # No se restaura el NOT NULL en downgrade: habría filas con equipo_id NULL
    # (líneas libres) que lo violarían. Es un downgrade best-effort.
