"""cliente_favoritos — equipos guardados por cliente

Revision ID: f1a9c7e3b5d2
Revises: e3f7a9c2b5d4
Create Date: 2026-05-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a9c7e3b5d2"
down_revision: Union[str, Sequence[str], None] = "e3f7a9c2b5d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cliente_favoritos (
            id         SERIAL PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            equipo_id  INTEGER NOT NULL REFERENCES equipos(id)  ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (cliente_id, equipo_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cf_cliente ON cliente_favoritos(cliente_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cf_equipo  ON cliente_favoritos(equipo_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS cliente_favoritos"))
