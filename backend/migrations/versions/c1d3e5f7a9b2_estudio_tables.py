"""estudio: tablas estudio y estudio_fotos (E1 — config + galería).

Revision ID: c1d3e5f7a9b2
Revises: a2b4c6d8e0f1
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d3e5f7a9b2"
down_revision: Union[str, Sequence[str], None] = "a2b4c6d8e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS estudio (
            id             SERIAL PRIMARY KEY,
            equipo_id      INTEGER,
            nombre         TEXT NOT NULL DEFAULT 'El Estudio',
            tagline        TEXT NOT NULL DEFAULT '',
            descripcion    TEXT NOT NULL DEFAULT '',
            precio_hora    INTEGER NOT NULL DEFAULT 0,
            min_horas      INTEGER NOT NULL DEFAULT 2,
            open_hour      INTEGER NOT NULL DEFAULT 8,
            close_hour     INTEGER NOT NULL DEFAULT 22,
            buffer_horas   INTEGER NOT NULL DEFAULT 0,
            pack_activo    BOOLEAN NOT NULL DEFAULT TRUE,
            pack_nombre    TEXT NOT NULL DEFAULT '',
            pack_descripcion TEXT NOT NULL DEFAULT '',
            pack_precio    INTEGER NOT NULL DEFAULT 0,
            features_json  TEXT,
            faq_json       TEXT,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS estudio_fotos (
            id          SERIAL PRIMARY KEY,
            estudio_id  INTEGER NOT NULL REFERENCES estudio(id) ON DELETE CASCADE,
            url         TEXT NOT NULL,
            path        TEXT,
            orden       INTEGER NOT NULL DEFAULT 0,
            es_principal BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_estudio_fotos_estudio_orden
        ON estudio_fotos(estudio_id, orden)
    """))


def downgrade() -> None:
    pass
