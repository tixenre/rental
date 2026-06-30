"""checkout — tabla aceptaciones_tyc (portero del checkout).

Registro inmutable de qué versión de T&C aceptó cada cliente. La versión
actual la controla `services.checkout.tyc.TYC_VERSION_ACTUAL` (hoy "v1").

Parte de f2cu1lun1qx01 (cuil unique index), el head activo al momento del
portero. El portero referencia `clientes`, que ya existía en ese head.

Espejo idempotente en `database.schema._init_db_schema`. MEMORIA 2026-06-03.

Revision ID: b1a2c3d4e5f6
Revises: f2cu1lun1qx01
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b1a2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2cu1lun1qx01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS aceptaciones_tyc (
            id          SERIAL PRIMARY KEY,
            cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            version     TEXT NOT NULL,
            aceptado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (cliente_id, version)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_aceptaciones_tyc_cliente "
        "ON aceptaciones_tyc(cliente_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_aceptaciones_tyc_cliente")
    op.execute("DROP TABLE IF EXISTS aceptaciones_tyc")
