"""cliente_listas — listas / kits personales del cliente

Revision ID: c1a5d7e9f3b2
Revises: f9a1c3e5b7d2
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a5d7e9f3b2"
down_revision: Union[str, Sequence[str], None] = "f9a1c3e5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cliente_listas (
            id          SERIAL PRIMARY KEY,
            cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            nombre      TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_cliente_listas_cliente ON cliente_listas(cliente_id)"
    ))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cliente_listas_items (
            id         SERIAL PRIMARY KEY,
            lista_id   INTEGER NOT NULL REFERENCES cliente_listas(id) ON DELETE CASCADE,
            equipo_id  INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            cantidad   INTEGER NOT NULL DEFAULT 1 CHECK (cantidad > 0),
            UNIQUE (lista_id, equipo_id)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_cliente_listas_items_lista ON cliente_listas_items(lista_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS cliente_listas_items"))
    conn.execute(sa.text("DROP TABLE IF EXISTS cliente_listas"))
