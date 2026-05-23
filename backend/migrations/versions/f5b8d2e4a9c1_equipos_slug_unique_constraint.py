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
    op.execute("DROP INDEX IF EXISTS idx_equipos_slug_unique")
    op.execute(
        "ALTER TABLE equipos "
        "ADD CONSTRAINT equipos_slug_key UNIQUE (slug)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE equipos DROP CONSTRAINT IF EXISTS equipos_slug_key")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_equipos_slug_unique "
        "ON equipos(slug) WHERE slug IS NOT NULL"
    )
