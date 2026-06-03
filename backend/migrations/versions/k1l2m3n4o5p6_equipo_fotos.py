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
    # Reparación de prod (#690): en prod preexistía una `equipo_fotos` LEGACY/ajena
    # con un esquema totalmente distinto (columnas `bytes`/`content_type` NOT NULL,
    # etc.) que `CREATE TABLE IF NOT EXISTS` no parchea y que el backfill (l1m2) no
    # puede poblar. Se detecta por la AUSENCIA de la columna canónica `url` y se
    # descarta. Una `equipo_fotos` canónica (que SÍ tiene `url`) nunca se toca →
    # seguro para cualquier entorno con datos. En prod se verificó 0 filas.
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'equipo_fotos'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'equipo_fotos'
                  AND column_name = 'url'
            ) THEN
                DROP TABLE equipo_fotos CASCADE;
            END IF;
        END $$;
    """))

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
