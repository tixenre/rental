"""media_assets: columna content_hash para dedup por hash (F0a)

Agrega `content_hash TEXT` (SHA-256 hex del original sin EXIF) + índice único
por (kind, content_hash) para dedup: si la misma imagen se sube dos veces al
mismo kind, store_upload devuelve el asset existente sin re-procesar ni re-subir.

Idempotente: ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
Espeja init_db() según MEMORIA 2026-06-03.

Revision ID: u2v3w4x5y6z7
Revises: t1h2u3m4b5
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u2v3w4x5y6z7"
down_revision: Union[str, Sequence[str], None] = "t1h2u3m4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        ALTER TABLE media_assets
        ADD COLUMN IF NOT EXISTS content_hash TEXT
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_media_assets_kind_hash
        ON media_assets(kind, content_hash)
        WHERE content_hash IS NOT NULL
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_media_assets_kind_hash"))
    op.execute(sa.text("ALTER TABLE media_assets DROP COLUMN IF EXISTS content_hash"))
