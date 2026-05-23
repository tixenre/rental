"""normalizacion: drop equipos.marca (TEXT) — brand_id (FK) es la fuente unica

equipos.marca (texto denormalizado) y brand_id (FK a marcas) eran datos
duplicados, y ni siquiera se mantenian en sync (el create seteaba marca pero
no brand_id). Consolidamos en brand_id: marcas.nombre es la fuente unica del
nombre de marca.

Backfill defensivo antes del DROP: por cada equipo con marca pero sin
brand_id, crea la marca si falta y linkea brand_id.

Revision ID: d5a8f2c4b6e9
Revises: d3f5a7c9e2b4
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d5a8f2c4b6e9"
down_revision: Union[str, Sequence[str], None] = "d3f5a7c9e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Solo si la columna marca todavía existe (idempotente).
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'equipos' AND column_name = 'marca'
            ) THEN
                -- Crear marcas faltantes a partir del texto legacy
                INSERT INTO marcas (nombre)
                SELECT DISTINCT TRIM(marca) FROM equipos
                WHERE marca IS NOT NULL AND TRIM(marca) <> ''
                ON CONFLICT (nombre) DO NOTHING;

                -- Backfill brand_id donde falte
                UPDATE equipos e SET brand_id = m.id
                FROM marcas m
                WHERE e.brand_id IS NULL
                  AND e.marca IS NOT NULL AND TRIM(e.marca) <> ''
                  AND LOWER(m.nombre) = LOWER(TRIM(e.marca));

                ALTER TABLE equipos DROP COLUMN marca;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS marca TEXT")
    op.execute("""
        UPDATE equipos e SET marca = m.nombre
        FROM marcas m WHERE m.id = e.brand_id
    """)
