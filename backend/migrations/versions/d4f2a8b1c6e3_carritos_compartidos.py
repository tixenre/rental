"""carritos_compartidos — compartir una composición por link (gaffer → productor)

Revision ID: d4f2a8b1c6e3
Revises: c1a5d7e9f3b2
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f2a8b1c6e3"
down_revision: Union[str, Sequence[str], None] = "c1a5d7e9f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS carritos_compartidos (
            id          SERIAL PRIMARY KEY,
            token       TEXT NOT NULL UNIQUE,
            titulo      TEXT,
            items_json  JSONB NOT NULL DEFAULT '[]',
            cliente_id  INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
            vistas      INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS carritos_compartidos"))
