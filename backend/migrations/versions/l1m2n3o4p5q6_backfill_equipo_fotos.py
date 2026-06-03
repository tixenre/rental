"""backfill equipo_fotos — una fila por equipo con foto_url existente (F3)

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, Sequence[str], None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO equipo_fotos (equipo_id, url, media_id, orden, es_principal)
        SELECT e.id, e.foto_url, NULL, 0, TRUE
        FROM equipos e
        WHERE e.foto_url IS NOT NULL
          AND e.foto_url <> ''
          AND NOT EXISTS (
              SELECT 1 FROM equipo_fotos ef WHERE ef.equipo_id = e.id
          )
    """))


def downgrade() -> None:
    # Solo borra filas sin media_id (las del backfill); deja las subidas con F2+
    op.execute(sa.text("""
        DELETE FROM equipo_fotos WHERE media_id IS NULL
    """))
