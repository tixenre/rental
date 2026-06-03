"""media_assets, media_variants + estudio_fotos.media_id (F1 pipeline no-destructivo)

Revision ID: i1j2k3l4m5n6
Revises: h1b2c3d4e5f6
Create Date: 2026-06-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i1j2k3l4m5n6"
down_revision: Union[str, Sequence[str], None] = "h1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS media_assets (
            id           BIGSERIAL PRIMARY KEY,
            kind         TEXT NOT NULL,
            original_key TEXT,
            original_ct  TEXT,
            width        INTEGER,
            height       INTEGER,
            bytes        INTEGER,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS media_variants (
            id           BIGSERIAL PRIMARY KEY,
            asset_id     BIGINT NOT NULL REFERENCES media_assets(id) ON DELETE CASCADE,
            name         TEXT NOT NULL,
            key          TEXT,
            url          TEXT,
            content_type TEXT NOT NULL DEFAULT 'image/webp',
            width        INTEGER,
            height       INTEGER,
            bytes        INTEGER,
            params       JSONB DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(asset_id, name)
        )
    """))

    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_media_variants_asset
        ON media_variants(asset_id)
    """))

    op.execute(sa.text("""
        ALTER TABLE estudio_fotos
        ADD COLUMN IF NOT EXISTS media_id BIGINT
        REFERENCES media_assets(id) ON DELETE SET NULL
    """))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE estudio_fotos DROP COLUMN IF EXISTS media_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS media_variants"))
    op.execute(sa.text("DROP TABLE IF EXISTS media_assets"))
