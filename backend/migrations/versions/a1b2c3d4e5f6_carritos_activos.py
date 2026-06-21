"""carritos_activos: persistencia server-side del carrito (#280 Fase 1).

Tabla nueva `carritos_activos`: persiste el estado del carrito del cliente
(logueado o anónimo) vía heartbeat desde el frontend. Permite ver en tiempo
real qué carritos están activos y analizar el funnel de conversión. El
`session_id` es un UUID v4 generado por el frontend (no requiere login).

Revision ID: a1b2c3d4e5f6
Revises: z0a1b2c3d4e5
Create Date: 2026-06-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS carritos_activos (
            id              SERIAL PRIMARY KEY,
            session_id      TEXT NOT NULL UNIQUE,
            cliente_id      INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            items_json      JSONB NOT NULL DEFAULT '[]',
            fecha_desde     DATE,
            fecha_hasta     DATE,
            hora_desde      TEXT,
            hora_hasta      TEXT,
            total_items     INTEGER NOT NULL DEFAULT 0,
            monto_estimado  INTEGER NOT NULL DEFAULT 0,
            confirmado      BOOLEAN NOT NULL DEFAULT FALSE,
            abandonado_en   TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_updated "
        "ON carritos_activos(updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_cliente "
        "ON carritos_activos(cliente_id) WHERE cliente_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_carritos_activos_no_conf "
        "ON carritos_activos(updated_at DESC) WHERE NOT confirmado"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS carritos_activos")
