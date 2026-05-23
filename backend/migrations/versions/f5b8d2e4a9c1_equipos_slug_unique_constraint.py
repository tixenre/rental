"""equipos.slug: partial UNIQUE index → UNIQUE constraint regular

La Fase 1 (e4a7c1f8d6b2) creó un UNIQUE index parcial
`idx_equipos_slug_unique ON equipos(slug) WHERE slug IS NOT NULL`. Eso
era seguro durante la transición (permite múltiples NULL), pero NO sirve
como árbitro de `ON CONFLICT (slug)` — Postgres exige un UNIQUE total o
parcial coincidente, lo que rompe los upserts del importer.

Postgres ya permite múltiples NULL en un UNIQUE constraint regular (los
trata como distintos por default), así que reemplazamos el partial index
por un UNIQUE constraint completo. Eso habilita `ON CONFLICT (slug)`
estándar.

Revision ID: f5b8d2e4a9c1
Revises: e4a7c1f8d6b2
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f5b8d2e4a9c1"
down_revision: Union[str, Sequence[str], None] = "e4a7c1f8d6b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente: si el constraint ya existe (re-corrida tras failure),
    # no tocamos nada. PostgreSQL no soporta ADD CONSTRAINT IF NOT EXISTS,
    # así que usamos un DO/EXCEPTION block.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'equipos_slug_key'
                  AND conrelid = 'equipos'::regclass
            ) THEN
                -- Defensive: detectar duplicates de slug non-NULL antes
                -- de ADD CONSTRAINT (que abortaría con error críptico).
                IF EXISTS (
                    SELECT 1 FROM equipos
                    WHERE slug IS NOT NULL
                    GROUP BY slug HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION 'Hay slugs duplicados en equipos. '
                        'Ejecutar: SELECT slug, COUNT(*) FROM equipos '
                        'WHERE slug IS NOT NULL GROUP BY slug HAVING COUNT(*) > 1; '
                        'y desambiguar antes de re-correr esta migración.';
                END IF;
                ALTER TABLE equipos ADD CONSTRAINT equipos_slug_key UNIQUE (slug);
            END IF;
        END $$;
    """)
    # Solo después de que el constraint nuevo esté garantizado, dropeamos
    # el partial index viejo. Si lo hiciéramos antes y ADD CONSTRAINT
    # fallara, quedaríamos sin ninguno de los dos y los ON CONFLICT (slug)
    # de import_all empezarían a fallar.
    op.execute("DROP INDEX IF EXISTS idx_equipos_slug_unique")


def downgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_equipos_slug_unique "
        "ON equipos(slug) WHERE slug IS NOT NULL"
    )
    op.execute("ALTER TABLE equipos DROP CONSTRAINT IF EXISTS equipos_slug_key")
