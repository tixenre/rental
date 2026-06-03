"""equipo_fotos: agregar columna url si la tabla fue creada sin ella

En algunos ambientes, equipo_fotos fue creada por una versión intermedia de
database.py que no incluía la columna url. La migración k1l2m3n4o5p6 usa
CREATE TABLE IF NOT EXISTS, por lo que silenciosamente no agrega la columna
si la tabla ya existe. Esta migración corrige eso de forma idempotente.

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-06-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n1o2p3q4r5s6"
down_revision: Union[str, Sequence[str], None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agrega url si no existe (idempotente). Para tablas recién creadas por
    # k1l2m3n4o5p6 ya tiene la columna — ADD COLUMN IF NOT EXISTS es no-op.
    op.execute(sa.text("""
        ALTER TABLE equipo_fotos
        ADD COLUMN IF NOT EXISTS url TEXT
    """))
    # Backfill: llenar url desde equipos.foto_url en filas que quedaron sin valor.
    op.execute(sa.text("""
        UPDATE equipo_fotos ef
           SET url = e.foto_url
          FROM equipos e
         WHERE ef.equipo_id = e.id
           AND ef.url IS NULL
           AND e.foto_url IS NOT NULL
           AND e.foto_url <> ''
    """))


def downgrade() -> None:
    pass
