"""estudio_trabajos: galería de producciones del estudio.

Cada trabajo tiene: título, realizador, logo, tipo (fotos|video), youtube_url,
galería de fotos (JSON), orden y flag activo.

Las fotos de cada trabajo se almacenan como JSON array de objetos
{url, url_sm, url_avif, url_sm_avif, path} en `fotos_json`.

Revision ID: a1b2c3d4e5f6
Revises: z0a1b2c3d4e5
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "estud1trabaj"
down_revision: Union[str, Sequence[str], None] = "z0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS estudio_trabajos (
            id                  SERIAL PRIMARY KEY,
            titulo              TEXT NOT NULL DEFAULT '',
            realizador          TEXT NOT NULL DEFAULT '',
            realizador_logo_url TEXT,
            tipo                TEXT NOT NULL DEFAULT 'fotos'
                            CHECK (tipo IN ('fotos', 'video')),
            youtube_url         TEXT,
            fotos_json          TEXT NOT NULL DEFAULT '[]',
            orden               INTEGER NOT NULL DEFAULT 0,
            activo              BOOLEAN NOT NULL DEFAULT TRUE,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_estudio_trabajos_orden ON estudio_trabajos(orden)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS estudio_trabajos"))
