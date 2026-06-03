"""backfill media_assets + media_variants para estudio_fotos sin media_id (F3)

Crea una fila `media_assets` (kind='estudio', original_key=NULL — el original
se perdió en el pipeline destructivo anterior) y una fila `media_variants`
(name='display') por cada foto de `estudio_fotos` que no tenga `media_id`.

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, Sequence[str], None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    rows = bind.execute(sa.text("""
        SELECT id, url, path
        FROM estudio_fotos
        WHERE media_id IS NULL
          AND url IS NOT NULL
          AND url <> ''
    """)).fetchall()

    for foto_id, url, path in rows:
        # key: use stored path if available, else derive from url
        key = path if path else url

        result = bind.execute(sa.text("""
            INSERT INTO media_assets (kind, original_key, original_ct, created_at, updated_at)
            VALUES ('estudio', NULL, 'image/webp', NOW(), NOW())
            RETURNING id
        """))
        asset_id = result.fetchone()[0]

        bind.execute(sa.text("""
            INSERT INTO media_variants (asset_id, name, key, url, content_type, created_at)
            VALUES (:asset_id, 'display', :key, :url, 'image/webp', NOW())
            ON CONFLICT (asset_id, name) DO NOTHING
        """), {"asset_id": asset_id, "key": key, "url": url})

        bind.execute(sa.text("""
            UPDATE estudio_fotos SET media_id = :asset_id WHERE id = :foto_id
        """), {"asset_id": asset_id, "foto_id": foto_id})


def downgrade() -> None:
    bind = op.get_bind()

    # Collect asset_ids linked to estudio_fotos rows that have no original_key (backfill marker)
    rows = bind.execute(sa.text("""
        SELECT ef.media_id
        FROM estudio_fotos ef
        JOIN media_assets ma ON ma.id = ef.media_id
        WHERE ma.original_key IS NULL AND ma.kind = 'estudio'
    """)).fetchall()

    bind.execute(sa.text("UPDATE estudio_fotos SET media_id = NULL WHERE media_id IS NOT NULL"))

    for (asset_id,) in rows:
        bind.execute(sa.text("DELETE FROM media_assets WHERE id = :id"), {"id": asset_id})
