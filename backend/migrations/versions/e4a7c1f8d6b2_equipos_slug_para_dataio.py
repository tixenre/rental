"""equipos.slug para sistema dataio (export/import por clave natural)

El nuevo módulo `backend/dataio/` usa `slug` como clave natural de equipos
en los JSONs versionados de `/data/catalog/`. Esta migración agrega la
columna como nullable + unique; el comando `python -m backend.dataio.cli
init-slugs` la puebla. Una segunda migración futura va a marcarla NOT NULL
una vez que todos los equipos tengan slug en todos los ambientes.

Revision ID: e4a7c1f8d6b2
Revises: d9e3f1a5c2b7
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e4a7c1f8d6b2"
down_revision: Union[str, Sequence[str], None] = "d9e3f1a5c2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE equipos ADD COLUMN IF NOT EXISTS slug VARCHAR(80)")
    # Índice UNIQUE parcial: permite múltiples NULLs durante la transición.
    # Cuando todos los equipos tengan slug, una migración posterior lo
    # convierte en NOT NULL y reemplaza el índice por UNIQUE completo.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_equipos_slug_unique "
        "ON equipos(slug) WHERE slug IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_equipos_slug_unique")
    op.execute("ALTER TABLE equipos DROP COLUMN IF EXISTS slug")
