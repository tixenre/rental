"""equipo_fotos (galería multi-foto de equipos) + marcas.media_id (F2)

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, Sequence[str], None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS equipo_fotos (
            id           SERIAL PRIMARY KEY,
            equipo_id    INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
            media_id     BIGINT REFERENCES media_assets(id) ON DELETE SET NULL,
            url          TEXT NOT NULL,
            path         TEXT,
            orden        INTEGER NOT NULL DEFAULT 0,
            es_principal BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_equipo_fotos_equipo_orden
        ON equipo_fotos(equipo_id, orden)
    """))

    op.execute(sa.text("""
        ALTER TABLE marcas
        ADD COLUMN IF NOT EXISTS media_id BIGINT REFERENCES media_assets(id) ON DELETE SET NULL
    """))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE marcas DROP COLUMN IF EXISTS media_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS equipo_fotos"))
